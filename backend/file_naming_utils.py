# utils/file_naming_utils.py
import os
import uuid
import time
from typing import List, Dict, Optional
import logging

# Set up logger
logger = logging.getLogger(__name__)

def generate_file_names(original_filename: str, toolname: str | None = None, ext: str | None = None) -> dict:
    """
    Generate secure file names for backend storage and frontend display.
    
    Args:
        original_filename (str): Original filename from user upload
        toolname (str | None, optional): Name of the tool if processing a file. Defaults to None.
        ext (str | None, optional): File extension override. Defaults to None.
        
    Returns:
        dict: Dictionary with display_name and stored_name
    """
    # Sanitize and extract extension
    if ext is None:
        _, file_ext = os.path.splitext(original_filename)
        ext = file_ext.lower() if file_ext else ''
    else:
        ext = f".{ext}" if not ext.startswith('.') else ext
        ext = ext.lower()
    
    # Generate unique components
    unique_id = uuid.uuid4().hex[:8] # Full UUID hex
    timestamp = str(int(time.time()))
    
    # Create stored filename based on whether it's a processed file or upload
    if toolname:
        # Processed file format: <toolname>_<uuid4>_<timestamp>.ext
        stored_name = f"{toolname}_{unique_id}_{timestamp}{ext}"
    else:
        # Upload file format: <uuid4>_<timestamp>.ext
        stored_name = f"{unique_id}_{timestamp}{ext}"
    
    # For display, use the original filename
    display_name = original_filename
    
    result = {
        "display_name": display_name,
        "stored_name": stored_name
    }
    
    logger.debug(f"Generated file names: {result}")
    return result

# For backward compatibility with existing code
def rename_processed_files(session_folder: str, session_files: Optional[List[Dict]] = None) -> int:
    """
    Rename files in the processed folder to format:
    toolused_originalfilename.pdf

    Assumes original filenames contain tool name and original filename separated by underscores,
    e.g. timestamp_originalfilename_toolname.pdf or similar.

    Args:
        session_folder (str): Absolute path to processed files folder.
        session_files (Optional[List[Dict]]): Optional session file info list (dicts with file metadata).

    Returns:
        int: Number of files renamed.
    """
    renamed_count = 0

    if not os.path.exists(session_folder):
        logger.error(f"Processed folder does not exist: {session_folder}")
        return renamed_count

    for filename in os.listdir(session_folder):
        file_path = os.path.join(session_folder, filename)
        if not os.path.isfile(file_path):
            continue

        # Skip if filename already matches desired pattern (toolname_originalfilename.pdf)
        if '_' in filename:
            parts = filename.rsplit('_', 2)
            if len(parts) == 3:
                # Example: timestamp_originalfilename_toolname.pdf
                timestamp_part, original_name_part, tool_name_part = parts
                # Compose new filename
                new_filename = f"{tool_name_part.replace('.pdf','')}_{original_name_part}.pdf"
            else:
                # If filename does not match expected pattern, skip
                continue
        else:
            # No underscores, skip
            continue

        new_file_path = os.path.join(session_folder, new_filename)

        # Avoid overwriting existing files
        if os.path.exists(new_file_path):
            logger.warning(f"File {new_filename} already exists, skipping rename of {filename}")
            continue

        try:
            os.rename(file_path, new_file_path)
            logger.info(f"Renamed {filename} -> {new_filename}")
            renamed_count += 1

            # Update session_files if provided
            if session_files is not None:
                for file_info in session_files:
                    if file_info.get('stored_name') == filename:
                        file_info['stored_name'] = new_filename
                        break

        except Exception as e:
            logger.error(f"Failed to rename {filename}: {e}")

    return renamed_count


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python file_naming_utils.py <processed_folder_path>")
        sys.exit(1)

    processed_folder_path = sys.argv[1]
    count = rename_processed_files(processed_folder_path)
    print(f"Renamed {count} files in {processed_folder_path}")
