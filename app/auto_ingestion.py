"""
Auto Ingestion Workflow Module
Handles automated document processing from monitored folders
"""

import os
import asyncio
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

from database import db
from file_handlers import handle_file
from main import assign_criticality_and_upload, load_criticality_config, config_file_path

logger = logging.getLogger(__name__)

# Global dictionary to track active workflows
active_workflows: Dict[int, asyncio.Task] = {}

# Maximum concurrent workflows (limit to 2 as per requirements)
MAX_CONCURRENT_WORKFLOWS = 2


def calculate_file_checksum(file_path: str) -> str:
    """Calculate MD5 checksum for file"""
    try:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating checksum for {file_path}: {e}")
        return ""


def rename_processed_file(file_path: str) -> str:
    """Rename file with timestamp suffix after processing"""
    try:
        path = Path(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"{path.stem}_{timestamp}_processed{path.suffix}"
        new_path = path.parent / new_name
        
        # Rename the file
        os.rename(file_path, new_path)
        logger.info(f"Renamed {file_path} to {new_path}")
        return str(new_path)
    except Exception as e:
        logger.error(f"Error renaming file {file_path}: {e}")
        return file_path


def scan_folder_for_files(workflow: Dict) -> List[Dict]:
    """Scan folder and return list of new files to process"""
    try:
        source_path = Path(workflow['source_path'])
        
        if not source_path.exists():
            logger.error(f"Source path does not exist: {source_path}")
            return []
        
        # Get file patterns (only PNG, JPG, JPEG)
        allowed_extensions = ['.png', '.jpg', '.jpeg']
        
        new_files = []
        
        # Scan directory (no subdirectories as per requirements)
        for file_path in source_path.iterdir():
            if not file_path.is_file():
                continue
            
            # Check if file extension is allowed
            if file_path.suffix.lower() not in allowed_extensions:
                continue
            
            # Calculate checksum
            checksum = calculate_file_checksum(str(file_path))
            if not checksum:
                continue
            
            # Check if file already exists in queue (by checksum)
            if db.check_file_exists_in_queue(workflow['id'], checksum):
                logger.debug(f"File already in queue (duplicate): {file_path.name}")
                continue
            
            # Add to list
            new_files.append({
                'file_path': str(file_path),
                'file_name': file_path.name,
                'file_size': file_path.stat().st_size,
                'file_checksum': checksum
            })
        
        return new_files
    
    except Exception as e:
        logger.error(f"Error scanning folder for workflow {workflow['id']}: {e}")
        return []


async def process_queue_item(queue_item: Dict, workflow: Dict, criticality_config: dict):
    """Process a single file from the queue"""
    queue_id = queue_item['id']
    workflow_id = workflow['id']
    file_path = queue_item['file_path']
    
    try:
        # Update queue status to processing
        db.update_queue_status(queue_id, 'processing')
        
        # Log start
        db.insert_workflow_log({
            'workflow_id': workflow_id,
            'queue_item_id': queue_id,
            'log_level': 'info',
            'log_message': f'Processing file: {queue_item["file_name"]}',
            'file_path': file_path
        })
        
        # Get user data for the workflow
        user_data = db.get_user_by_id(workflow['user_id'])
        if not user_data:
            raise Exception(f"User not found for workflow: {workflow['user_id']}")
        
        processing_start_time = datetime.now()
        
        # Process file (AI classification)
        result = handle_file(file_path)
        
        # Assign criticality and upload to FileNet
        result = assign_criticality_and_upload(file_path, result, criticality_config)
        
        processing_end_time = datetime.now()
        
        # Save to database (AI document classifications)
        from db_integration import data_manager
        document_id = data_manager.save_ai_document_processing(
            file_path, result, processing_start_time, processing_end_time, user_data
        )
        
        # Update queue status to completed
        db.update_queue_status(queue_id, 'completed', document_id=document_id)
        
        # Rename the processed file
        new_file_path = rename_processed_file(file_path)
        
        # Update workflow stats
        db.increment_workflow_stats(workflow_id, success=True)
        
        # Log success
        db.insert_workflow_log({
            'workflow_id': workflow_id,
            'queue_item_id': queue_id,
            'log_level': 'success',
            'log_message': f'Successfully processed: {queue_item["file_name"]}',
            'file_path': new_file_path,
            'details': {
                'document_type': result.get('document_type'),
                'criticality': result.get('criticality'),
                'document_id': document_id
            }
        })
        
        logger.info(f"Successfully processed file: {queue_item['file_name']}")
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error processing queue item {queue_id}: {error_message}")
        
        # Increment retry count
        queue_item['retry_count'] += 1
        
        # Check if max retries reached
        if queue_item['retry_count'] >= queue_item['max_retries']:
            # Mark as failed permanently
            db.update_queue_status(queue_id, 'failed', error_message=error_message)
            
            # Update workflow stats
            db.increment_workflow_stats(workflow_id, success=False)
            
            # Stop the workflow (as per requirements)
            db.update_workflow_status(workflow_id, 'stopped', 
                                     error_message=f"Max retries reached for file: {queue_item['file_name']}")
            
            # Log error
            db.insert_workflow_log({
                'workflow_id': workflow_id,
                'queue_item_id': queue_id,
                'log_level': 'error',
                'log_message': f'Failed after {queue_item["max_retries"]} retries: {queue_item["file_name"]}',
                'file_path': file_path,
                'details': {'error': error_message}
            })
            
            # Signal to stop workflow
            raise Exception(f"Max retries reached, stopping workflow")
        else:
            # Retry
            db.increment_retry_count(queue_id)
            
            # Log warning
            db.insert_workflow_log({
                'workflow_id': workflow_id,
                'queue_item_id': queue_id,
                'log_level': 'warning',
                'log_message': f'Processing failed (retry {queue_item["retry_count"]}/{queue_item["max_retries"]}): {queue_item["file_name"]}',
                'file_path': file_path,
                'details': {'error': error_message}
            })


async def workflow_scanner_task(workflow_id: int):
    """Background task that runs continuously for a workflow"""
    logger.info(f"Starting workflow scanner for workflow {workflow_id}")
    
    try:
        while workflow_id in active_workflows:
            # Get current workflow data
            workflow = db.get_workflow_by_id(workflow_id)
            
            if not workflow or workflow['status'] != 'running':
                logger.info(f"Workflow {workflow_id} stopped or not found")
                break
            
            # Load criticality config
            criticality_config = load_criticality_config(config_file_path)
            
            try:
                # Log scan start
                db.insert_workflow_log({
                    'workflow_id': workflow_id,
                    'log_level': 'info',
                    'log_message': 'Starting folder scan'
                })
                
                # Scan folder for new files
                new_files = scan_folder_for_files(workflow)
                
                # Add new files to queue
                for file_info in new_files:
                    try:
                        queue_id = db.add_to_queue({
                            'workflow_id': workflow_id,
                            'file_path': file_info['file_path'],
                            'file_name': file_info['file_name'],
                            'file_size': file_info['file_size'],
                            'file_checksum': file_info['file_checksum']
                        })
                        
                        logger.info(f"Added to queue: {file_info['file_name']}")
                        
                        # Log file added
                        db.insert_workflow_log({
                            'workflow_id': workflow_id,
                            'log_level': 'info',
                            'log_message': f'File added to queue: {file_info["file_name"]}',
                            'file_path': file_info['file_path']
                        })
                    except Exception as e:
                        logger.error(f"Error adding file to queue: {e}")
                
                # Update scan timestamp
                db.update_workflow_scan_time(workflow_id)
                
                # Process one file from queue
                pending_item = db.get_next_pending_item(workflow_id)
                
                if pending_item:
                    await process_queue_item(pending_item, workflow, criticality_config)
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error in workflow scanner: {error_msg}")
                
                # Check if it's a max retry error (should stop workflow)
                if "Max retries reached" in error_msg:
                    logger.info(f"Stopping workflow {workflow_id} due to max retries")
                    break
                
                # Log error
                db.insert_workflow_log({
                    'workflow_id': workflow_id,
                    'log_level': 'error',
                    'log_message': f'Workflow error: {error_msg}'
                })
            
            # Sleep for the specified interval
            await asyncio.sleep(workflow['interval_seconds'])
    
    except asyncio.CancelledError:
        logger.info(f"Workflow {workflow_id} scanner cancelled")
    
    except Exception as e:
        logger.error(f"Fatal error in workflow scanner for {workflow_id}: {e}")
        db.update_workflow_status(workflow_id, 'error', error_message=str(e))
    
    finally:
        # Cleanup
        if workflow_id in active_workflows:
            del active_workflows[workflow_id]
        
        # Update status to stopped if not already in error
        workflow = db.get_workflow_by_id(workflow_id)
        if workflow and workflow['status'] == 'running':
            db.update_workflow_status(workflow_id, 'stopped')
        
        logger.info(f"Workflow scanner stopped for workflow {workflow_id}")


def start_workflow(workflow_id: int) -> bool:
    """Start a workflow"""
    try:
        # Check if already running
        if workflow_id in active_workflows:
            logger.warning(f"Workflow {workflow_id} is already running")
            return False
        
        # Check concurrent workflow limit
        if len(active_workflows) >= MAX_CONCURRENT_WORKFLOWS:
            raise Exception(f"Maximum concurrent workflows ({MAX_CONCURRENT_WORKFLOWS}) reached")
        
        # Get workflow
        workflow = db.get_workflow_by_id(workflow_id)
        if not workflow:
            raise Exception(f"Workflow {workflow_id} not found")
        
        # Validate source path
        if not os.path.exists(workflow['source_path']):
            raise Exception(f"Source path does not exist: {workflow['source_path']}")
        
        # Update status to running
        db.update_workflow_status(workflow_id, 'running')
        
        # Create background task
        task = asyncio.create_task(workflow_scanner_task(workflow_id))
        active_workflows[workflow_id] = task
        
        # Log start
        db.insert_workflow_log({
            'workflow_id': workflow_id,
            'log_level': 'success',
            'log_message': f'Workflow started: {workflow["workflow_name"]}'
        })
        
        logger.info(f"Started workflow {workflow_id}")
        return True
    
    except Exception as e:
        logger.error(f"Error starting workflow {workflow_id}: {e}")
        db.update_workflow_status(workflow_id, 'stopped', error_message=str(e))
        raise


async def stop_workflow(workflow_id: int) -> bool:
    """Stop a workflow"""
    try:
        # Check if running
        if workflow_id not in active_workflows:
            logger.warning(f"Workflow {workflow_id} is not running")
            # Update status anyway
            db.update_workflow_status(workflow_id, 'stopped')
            return True
        
        # Get workflow
        workflow = db.get_workflow_by_id(workflow_id)
        if not workflow:
            return False
        
        # Cancel the task
        task = active_workflows[workflow_id]
        task.cancel()
        
        # Wait for task to complete (finish current file)
        try:
            await asyncio.wait_for(task, timeout=60.0)
        except asyncio.TimeoutError:
            logger.warning(f"Workflow {workflow_id} did not stop gracefully within timeout")
        except asyncio.CancelledError:
            pass
        
        # Remove from active workflows
        if workflow_id in active_workflows:
            del active_workflows[workflow_id]
        
        # Update status
        db.update_workflow_status(workflow_id, 'stopped')
        
        # Log stop
        db.insert_workflow_log({
            'workflow_id': workflow_id,
            'log_level': 'info',
            'log_message': f'Workflow stopped: {workflow["workflow_name"]}'
        })
        
        logger.info(f"Stopped workflow {workflow_id}")
        return True
    
    except Exception as e:
        logger.error(f"Error stopping workflow {workflow_id}: {e}")
        return False


def get_active_workflow_count() -> int:
    """Get count of currently active workflows"""
    return len(active_workflows)


def is_workflow_running(workflow_id: int) -> bool:
    """Check if workflow is currently running"""
    return workflow_id in active_workflows

