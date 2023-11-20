import os

from my_logger import CustomLogger

vlog = CustomLogger("cleanup", verbose=True, log_dir="logs")


def remove_log_files(file_paths: list):
    """
    Performs delete operations on the listing file paths
    :param file_paths:
    :return:
    """
    current_directory = os.path.dirname(os.path.realpath(__file__))
    parent_directory = os.path.abspath(os.path.join(current_directory, os.pardir))
    for f in file_paths:
        fp = os.path.join(parent_directory, "logs", f)
        try:
            # Attempt to delete the file
            os.remove(fp)
            vlog.info(f"File {fp} has been deleted.")
        except FileNotFoundError:
            vlog.error(f"File {fp} not found. It cannot be deleted.")
        except Exception as e:
            vlog.error(f"An error occurred: {e}")


def get_scraper_names() -> list[str]:
    """
    return a list of scraper names from scraper/
    :return:
    """
    # List all files in the directory
    files = os.listdir("./scraper")

    # Iterate through the files and print their names without extensions
    scraper_names = []
    for file in files:
        file_name, file_extension = os.path.splitext(file)
        if file_extension == ".py" and file_name != "__init__":
            scraper_names.append(file_name)
    return scraper_names


def get_scraper_log_files_by_name(scraper_name: str) -> list[str]:
    """
    return list of log file paths of the given scraper
    :param scraper_name:
    :return:
    """
    log_files = []
    files = os.listdir("./logs")
    for file in files:
        file_name, file_extension = os.path.splitext(file)
        if file_extension == ".log" and file_name.startswith(scraper_name):
            log_files.append(file_name + file_extension)
    return log_files


def cleanup_logs():
    """

    :return:
    """
    scrapers = get_scraper_names()
    for scraper_name in scrapers:
        file_paths = get_scraper_log_files_by_name(scraper_name)
        file_paths.sort(reverse=True)
        if len(file_paths) > 10:
            # only keep the first 10 files
            remove_log_files(file_paths[10:])


if __name__ == "__main__":
    cleanup_logs()
