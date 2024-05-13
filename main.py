import os
import sys
import ctypes
import logging
import requests
from bs4 import BeautifulSoup
from PyQt5.QtGui import QIcon
from ui import (
    QtWidgets,
    Ui_MainWindow)
from downloader import (
    Downloader,
    SingleDownload)
from PyQt5.QtWidgets import (
    QMainWindow,
    QApplication,
    QHeaderView,
    QFileDialog,
    QMessageBox,
    QPushButton,
    QTableWidgetItem)
from PyQt5.QtCore import (
    pyqtSlot,
    QSettings,
    QObject,
    QThread,
    QFile,
    pyqtSignal)


class PlaylistWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int)

    def __init__(self, playlist_id: str | list, settings: str) -> None:
        super().__init__()
        self.playlist_id: str | list = playlist_id
        self.settings: str = settings

    def run(self):
        downloader: Downloader = Downloader()
        downloader.download(self.playlist_id, self.settings)
        self.finished.emit()


class SingleWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int)

    def __init__(self, video_id: str | list, settings: str) -> None:
        super().__init__()
        self.video_id: str | list = video_id
        self.settings: str  = settings

    def run(self):
        downloader: SingleDownload = SingleDownload()
        downloader.download(self.video_id, self.settings)
        self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        logging.basicConfig(filename='error.log', level=logging.ERROR)
        self.ui: Ui_MainWindow = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.stackedMainView.setCurrentIndex(0)
        self.settings = QSettings('YTmusic-dl', 'YTmusic-dl')
        self.load_settings()
        font = self.ui.app_label.font()
        font.setBold(True)
        font.setPointSize(14)
        self.ui.app_label.setFont(font)
        self.ui.app_label.setText("YTmusic-dl")
        self.ui.tableWidget.setColumnWidth(0, 463)
        self.ui.tableWidget.itemDoubleClicked.connect(self.open_path)
        self.ui.search_bar.textChanged.connect(self.filter_table)
        self.ui.single_dl_btn.setEnabled(False)
        self.ui.bulk_dl.setEnabled(False)
        self.ui.bulk_add.setEnabled(False)
        self.ui.single_input.textChanged.connect(self.enabledownload)
        self.ui.bulk_edit.textChanged.connect(self.enableurledit)
        self.download_queue: list = []

    def enableurledit(self):
        if len(self.ui.bulk_edit.text()) > 5:
            self.ui.bulk_add.setEnabled(True)
        else:
            self.ui.bulk_add.setEnabled(False)

    def enabledownload(self):
        if len(self.ui.single_input.text()) > 5:
            self.ui.single_dl_btn.setEnabled(True)
        else:
            self.ui.single_dl_btn.setEnabled(False)

    def open_path(self, item: QTableWidgetItem):
        folder: str = item.text()
        directory: str = self.settings.value('Path')
        path: str = os.path.join(directory, folder)
        if os.path.exists(path):
            if sys.platform == 'win32':
                if path.startswith('//'):
                    path: str = f"\\{path[2:]}"
                    os.startfile(path)
                else:
                    os.startfile(path)
            elif sys.platform == 'darwin':
                os.system(f'open "{path}"')
            elif sys.platform == 'linux':
                os.system(f'xdg-open "{path}"')

    def downloader_task(self, playlist_id: str, settings: str):
        self.thread: QThread = QThread()
        self.worker: PlaylistWorker = PlaylistWorker(playlist_id, settings)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.finished.connect(self.enable_single_dl_btn)
        self.thread.start()

    def single_downloader_task(self, video_id: str, settings: str):
        self.thread: QThread = QThread()
        self.worker: SingleWorker = SingleWorker(video_id, settings)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.finished.connect(self.enable_single_dl_btn)
        self.thread.start()

    def load_settings(self):
        if self.settings.contains("Path"):
            Path: str = self.settings.value("Path")
            self.ui.folder_path_line.setText(Path)

    def populate_table(self):
        try:
            directory: str = self.settings.value("Path")
            folders: str = os.listdir(directory)
            self.ui.tableWidget.setRowCount(len(folders))
            self.ui.tableWidget.horizontalHeader().setSectionResizeMode(1) 
            albums: int = 0
            tracks: int = 0
            for row, folder in enumerate(folders):
                self.ui.tableWidget.setItem(row, 0, QTableWidgetItem(folder))
                if folder.endswith(".mp3"):
                    tracks += 1
                if "." not in folder:
                    albums += 1
            self.ui.total_tracks.setText(f"Total Tracks: {tracks}")
            self.ui.total_albums.setText(f"Total Albums: {albums}")
        except Exception:
            pass

    def filter_table(self):
        search_text: str = self.ui.search_bar.text().lower()
        albums: int = 0
        tracks: int = 0
        for row in range(self.ui.tableWidget.rowCount()):
            row_visible: bool = False
            for col in range(self.ui.tableWidget.columnCount()):
                item = self.ui.tableWidget.item(row, col)
                if item is not None and search_text in item.text().lower():
                    row_visible: bool = True
                    line: str = item.text().lower()
                    if line.endswith("mp3"):
                        tracks += 1
                    if "." not in line:
                        albums += 1
                    break
            self.ui.tableWidget.setRowHidden(row, not row_visible)
            self.ui.total_albums.setText(f"Total Albums: {albums}")
            self.ui.total_tracks.setText(f"Total Tracks: {tracks}")

    @pyqtSlot()
    def on_single_btn_clicked(self):
        self.ui.stackedMainView.setCurrentIndex(0)
        self.ui.folder_btn.setChecked(False)
        self.ui.bulk_btn.setChecked(False)

    @pyqtSlot()
    def on_bulk_btn_clicked(self):
        self.ui.stackedMainView.setCurrentIndex(1)
        self.ui.single_btn.setChecked(False)
        self.ui.folder_btn.setChecked(False)
        self.ui.bulk_table.setColumnCount(3)
        header: QtWidgets.QHeaderView = self.ui.bulk_table.horizontalHeader()
        self.ui.bulk_table.setHorizontalHeaderLabels(['Title', 'Type', ''])
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

    @pyqtSlot()
    def on_bulk_add_clicked(self):

        def get_title(url) -> str:
            if url.startswith("http"):
                response: requests.models.Response = requests.get(url)
                video_id: str = url.split("=")[1]
                if len(video_id) > 11:
                    link = f"https://www.youtube.com/playlist?list={video_id}"
                    response: requests.models.Response = requests.get(link)
                else:
                    link = f"https://www.youtube.com/watch?v={video_id}"
                    response: requests.models.Response = requests.get(link)
            else:
                if len(url) > 11:
                    link = f"https://www.youtube.com/playlist?list={url}"
                    response: requests.models.Response = requests.get(link)
                else:
                    link = f"https://www.youtube.com/watch?v={url}"
                    response: requests.models.Response = requests.get(link)
            if response.status_code == 200:
                page_source = response.text
                soup: BeautifulSoup = BeautifulSoup(page_source, 'html.parser')
                title: str = soup.find('title').string.strip()
            return title

        self.ui.bulk_dl.setEnabled(True)
        try:
            self.ui.bulk_table.setRowCount(len(self.download_queue) + 1)
            url = self.ui.bulk_edit.text()
            title: str = get_title(url)
            try:
                video_id: str = url.split("=")[1]
            except Exception:
                pass
            remove_btn: QPushButton = QPushButton("delete")
            self.ui.bulk_edit.clear()
            self.download_queue.append({'title': title, 'type': "playlist" if len(video_id) > 11 else "single", 'button': remove_btn, 'id': video_id})
            remove_btn.clicked.connect(lambda: self.remove_row())
            self.populate_bulktable()
            self.ui.bulk_table.resizeColumnToContents(0)
        except Exception as e:
            self.error_modal(e)

    def populate_bulktable(self):
        for index, rows in enumerate(self.download_queue):
            for num, k in enumerate(rows):
                if num == 3:
                    continue
                if num == 2:
                    self.ui.bulk_table.setCellWidget(index, num, rows[k])
                    continue
                self.ui.bulk_table.setItem(index, num, QTableWidgetItem(rows[k]))

    @pyqtSlot()
    def remove_row(self):
        index: int = self.ui.bulk_table.currentRow()
        self.ui.bulk_table.removeRow(index)
        del self.download_queue[index]

    @pyqtSlot()
    def on_bulk_dl_clicked(self):
        singles: list = [track for track in self.download_queue if track["type"] == "single"]
        playlists: list = [track for track in self.download_queue if track["type"] == "playlist"]
        self.expected = len(singles + playlists)
        self.current = 0
        self.ui.bulk_dl.setEnabled(False)
        self.ui.clear_dl.setEnabled(False)
        self.thread: QThread = QThread()
        self.worker: SingleWorker = SingleWorker(singles, self.settings.value('Path'))
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.finished.connect(lambda x=len(singles): self.trackprogress(x))
        self.worker.finished.connect(self.enable_bulk_dl_btn)
        self.thread.start()

        self.threadtwo: QThread = QThread()
        self.workertwo: PlaylistWorker = PlaylistWorker(playlists, self.settings.value('Path'))
        self.workertwo.moveToThread(self.threadtwo)
        self.threadtwo.started.connect(self.workertwo.run)
        self.workertwo.finished.connect(self.threadtwo.quit)
        self.workertwo.finished.connect(self.workertwo.deleteLater)
        self.threadtwo.finished.connect(self.threadtwo.deleteLater)
        self.workertwo.finished.connect(lambda x=len(playlists): self.trackprogress(x))
        self.workertwo.finished.connect(self.enable_bulk_dl_btn)
        self.threadtwo.start()
        self.ui.bulk_dl.setText("Downloading...")

    @pyqtSlot()
    def on_clear_dl_clicked(self):
        for n in range(len(self.download_queue), -1, -1):
            self.ui.bulk_table.removeRow(n)
        self.download_queue = []
        self.populate_bulktable()

    @pyqtSlot()
    def on_folder_btn_clicked(self):
        self.ui.stackedMainView.setCurrentIndex(2)
        self.ui.single_btn.setChecked(False)
        self.ui.bulk_btn.setChecked(False)
        self.populate_table()

    @pyqtSlot()
    def on_single_dl_btn_clicked(self):
        url: str = self.ui.single_input.text()
        if url.startswith("http"):
            video_id: str = url.split("=")[1]
        else:
            video_id: str = url
        if not self.settings.contains('Path') or len(self.settings.value('Path')) < 4:
            self.error_modal()
        else:
            self.ui.single_dl_btn.setEnabled(False)
            self.ui.single_dl_btn.setText("Downloading...")
            if len(video_id) > 11:
                self.downloader_task(video_id, self.settings.value('Path'))
            else:
                self.single_downloader_task(video_id, self.settings.value('Path'))

    def trackprogress(self, num: int):
        self.current += num

    def enable_single_dl_btn(self):
        self.ui.single_dl_btn.setEnabled(True)
        self.ui.single_dl_btn.setText("Download")
        self.ui.single_input.clear()

    def enable_bulk_dl_btn(self):
        if self.current == self.expected:
            self.ui.bulk_dl.setEnabled(True)
            self.ui.clear_dl.setEnabled(True)
            self.ui.bulk_dl.setText("Download All")

    @pyqtSlot()
    def on_folder_browse_btn_clicked(self):
        file: str = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        self.ui.folder_path_line.setText(file)
        self.settings.setValue('Path', file)
        if self.settings.value('Path') != '':
            self.populate_table()

    @pyqtSlot()
    def on_clear_search_clicked(self):
        self.ui.search_bar.clear()

    def error_modal(self, e=None):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        if e is None:
            msg.setText("Define a folder path to download files")
        else:
            msg.setText("Invalid URL")
        msg.setWindowTitle("Error")
        msg.exec_()

if __name__ == "__main__":
    basedir = os.path.dirname(__file__)
    try:
        if sys.platform == 'win32':
            myappid = 'mycompany.myproduct.subproduct.version'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        app: QApplication = QApplication(sys.argv)
        window: MainWindow = MainWindow()
        window.setWindowTitle("YTmusic-dl")
        window.setWindowIcon(QIcon(os.path.join(basedir, 'icons/logo64.png')))
        styles = QFile(os.path.join(basedir, "styles/styles.qss"))
        styles.open(QFile.OpenModeFlag.ReadOnly)
        stylesheet = styles.readAll().data().decode("utf-8")
        window.setStyleSheet(stylesheet)
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        logging.exception(str(e))
