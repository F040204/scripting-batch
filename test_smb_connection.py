#!/usr/bin/env python3
"""
Test script to verify SMB connection is working.
This script attempts to connect to the SMB server and read data.
"""
import os
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("Loaded environment variables from .env file")
except ImportError:
    logger.info("python-dotenv not installed, using system environment variables")

# Import SMB modules
try:
    import smbprotocol
    from smbprotocol.connection import Connection
    from smbprotocol.session import Session
    from smbprotocol.tree import TreeConnect
    from smbprotocol.open import Open, CreateDisposition
    from smbprotocol.exceptions import SMBException
    logger.info("✓ SMB modules imported successfully")
except ImportError as e:
    logger.error(f"✗ Failed to import SMB modules: {e}")
    logger.error("Install required packages: pip install smbprotocol")
    sys.exit(1)

import uuid

def test_smb_connection():
    """Test SMB connection and return status"""
    
    # Get configuration from environment variables
    SMB_SERVER = os.environ.get('SMB_SERVER', '172.16.11.104')
    SMB_SHARE = os.environ.get('SMB_SHARE', 'pond')
    SMB_USERNAME = os.environ.get('SMB_USERNAME', '')
    SMB_PASSWORD = os.environ.get('SMB_PASSWORD', '')
    SMB_BASE_PATH = os.environ.get('SMB_BASE_PATH', 'incoming/Orexplore')
    
    logger.info("=" * 70)
    logger.info("SMB CONNECTION TEST")
    logger.info("=" * 70)
    logger.info(f"Server: {SMB_SERVER}")
    logger.info(f"Share: {SMB_SHARE}")
    logger.info(f"Username: {SMB_USERNAME if SMB_USERNAME else '(empty - anonymous)'}")
    logger.info(f"Password: {'***' if SMB_PASSWORD else '(empty)'}")
    logger.info(f"Base Path: {SMB_BASE_PATH}")
    logger.info("-" * 70)
    
    conn = None
    smb_session = None
    tree = None
    
    try:
        # Step 1: Create connection
        logger.info("Step 1: Establishing TCP connection to SMB server...")
        conn = Connection(uuid.uuid4(), SMB_SERVER, 445)
        conn.connect()
        logger.info("✓ TCP connection established")
        
        # Step 2: Create session (authenticate)
        logger.info("Step 2: Authenticating with SMB server...")
        smb_session = Session(conn, username=SMB_USERNAME, password=SMB_PASSWORD)
        smb_session.connect()
        logger.info("✓ SMB session authenticated successfully")
        
        # Step 3: Connect to share
        logger.info(f"Step 3: Connecting to share: \\\\{SMB_SERVER}\\{SMB_SHARE}")
        tree = TreeConnect(smb_session, fr"\\{SMB_SERVER}\{SMB_SHARE}")
        tree.connect()
        logger.info("✓ Successfully connected to share")
        
        # Step 4: Try to read base directory
        logger.info(f"Step 4: Accessing base directory: {SMB_BASE_PATH}")
        base_dir = Open(tree, SMB_BASE_PATH)
        base_dir.create(CreateDisposition.FILE_OPEN)
        logger.info("✓ Base directory accessible")
        
        # Step 5: List contents
        logger.info("Step 5: Listing directory contents...")
        item_count = 0
        for info in base_dir.query_directory("*"):
            item_count += 1
            if item_count <= 5:  # Show first 5 items
                logger.info(f"  - {info.file_name}")
        
        if item_count > 5:
            logger.info(f"  ... and {item_count - 5} more items")
        
        logger.info(f"✓ Found {item_count} items in base directory")
        base_dir.close()
        
        # Step 6: Test reading batch data
        logger.info("Step 6: Testing batch data reading...")
        batches_found = 0
        
        base_dir = Open(tree, SMB_BASE_PATH)
        base_dir.create(CreateDisposition.FILE_OPEN)
        
        for info in base_dir.query_directory("*"):
            hole_id = info.file_name
            
            if "." in hole_id:
                continue
            
            hole_path = f"{SMB_BASE_PATH}/{hole_id}"
            
            try:
                hole_dir = Open(tree, hole_path)
                hole_dir.create(CreateDisposition.FILE_OPEN)
                
                for batch_info in hole_dir.query_directory("*"):
                    batch_folder = batch_info.file_name
                    
                    if not batch_folder.startswith("batch-"):
                        continue
                    
                    batches_found += 1
                    if batches_found <= 3:  # Show first 3 batches
                        logger.info(f"  - Found batch: {hole_id}/{batch_folder}")
                
                hole_dir.close()
            except SMBException:
                continue
        
        base_dir.close()
        logger.info(f"✓ Found {batches_found} batch folders")
        
        logger.info("=" * 70)
        logger.info("✓ SMB CONNECTION TEST PASSED")
        logger.info("=" * 70)
        return True
        
    except SMBException as e:
        logger.error("=" * 70)
        logger.error("✗ SMB CONNECTION TEST FAILED")
        logger.error("=" * 70)
        logger.error(f"SMB Error: {e}")
        logger.error("")
        logger.error("Possible causes:")
        logger.error("  1. Wrong username or password")
        logger.error("  2. Server is not reachable (check network/firewall)")
        logger.error("  3. Share name is incorrect")
        logger.error("  4. User doesn't have permission to access the share")
        logger.error("")
        logger.error("Verify your .env file configuration:")
        logger.error(f"  SMB_SERVER={SMB_SERVER}")
        logger.error(f"  SMB_SHARE={SMB_SHARE}")
        logger.error(f"  SMB_USERNAME={SMB_USERNAME}")
        logger.error(f"  SMB_PASSWORD=(check if set)")
        return False
        
    except Exception as e:
        logger.error("=" * 70)
        logger.error("✗ UNEXPECTED ERROR")
        logger.error("=" * 70)
        logger.error(f"Error: {e}")
        logger.error(f"Type: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        return False
        
    finally:
        # Cleanup
        if tree:
            try:
                tree.disconnect()
                logger.info("Disconnected from share")
            except Exception:
                pass
        if smb_session:
            try:
                smb_session.disconnect()
                logger.info("Closed SMB session")
            except Exception:
                pass
        if conn:
            try:
                conn.disconnect()
                logger.info("Closed TCP connection")
            except Exception:
                pass

if __name__ == "__main__":
    success = test_smb_connection()
    sys.exit(0 if success else 1)
