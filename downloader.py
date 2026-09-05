from pathlib import Path
import re
import gdown

##
# @class GoogleDriveDownloader
# @brief Utility class for automating downloads of complete Google Drive folder structures using gdown.
#
# Validates input URLs to ensure they point to valid Google Drive folders (rather than single files)
# and manages destination directory creation and file retrieval.
class GoogleDriveDownloader:

    FOLDER_URL_PATTERN = re.compile(
        r"https://drive\.google\.com/drive/(?:u/\d+/)?folders/([a-zA-Z0-9_-]+)"
    )

    ##
    # @brief Initializes the downloader instance and creates the output directory if needed.
    #
    # @param output_dir Base directory path where downloaded files will be stored (defaults to current working directory ".").
    # @param quiet If True, suppresses download progress logs and gdown output in terminal.
    def __init__(self, output_dir: str = ".", quiet: bool = False):
        self.output_dir = Path(output_dir)
        self.quiet = quiet
        self.output_dir.mkdir(parents=True, exist_ok=True)

    ##
    # @brief Validates and downloads an entire Google Drive folder to the specified target directory.
    #
    # @param folder_url Full Google Drive URL pointing to a shared folder.
    # @param destination_folder Optional subfolder inside output_dir where files will be placed.
    # @return Result object/list returned by gdown containing paths of downloaded files.
    # @raise ValueError If folder_url is invalid or points to a file instead of a folder.
    def download_all(self, folder_url: str, destination_folder: str | None = None):
        folder_url = folder_url.strip()

        if not self._is_folder_url(folder_url):
            raise ValueError("You must provide a Google Drive folder URL, not a file URL.")

        target_dir = self.output_dir

        if destination_folder:
            target_dir = self.output_dir / destination_folder
            target_dir.mkdir(parents=True, exist_ok=True)

        result = gdown.download_folder(
            url=folder_url,
            output=str(target_dir),
            quiet=self.quiet,
            use_cookies=False,
        )

        return result

    ##
    # @brief Internal helper to verify if a URL string matches the expected Google Drive folder pattern.
    #
    # @param url URL string to check.
    # @return True if URL corresponds to a Google Drive folder, False otherwise.
    def _is_folder_url(self, url: str) -> bool:
        return bool(self.FOLDER_URL_PATTERN.search(url))
