from library_of_h.downloader.base_classes.service_downloader import \
    ServiceDownloaderBase
from library_of_h.logger import MainType, ServiceType, SubType, get_logger


class nhentaiDownloader(ServiceDownloaderBase):
    def __init__(self) -> None:
        super().__init__()

        self._logger = get_logger(
            main_type=MainType.DOWNLOADER,
            service_type=ServiceType.NHENTAI,
            sub_type=SubType.DLDR,
        )
