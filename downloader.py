import os
import re
import logging
import contextlib
import subprocess
import multiprocessing
from pytube import YouTube
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from moviepy.config import get_setting
from moviepy.tools import subprocess_call

class Base:
    def __init__(self) -> None:
        logging.basicConfig(filename='error.log', level=logging.ERROR)

    def ffmpeg_extract_audio(self, inputfile: str, output: str, bitrate=3000, fps=44100):
        """ extract the sound from a video file and save it in ``output`` """
        cmd = [get_setting("FFMPEG_BINARY"), "-y", "-i", inputfile, "-ab", "%dk"%bitrate,
            "-ar", "%d"%fps, output]
        subprocess_call(cmd, logger=None)

    def create_directory(self, directory_path: str) -> bool:
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
            #print(f"Directory '{directory_path}' created.")
            return True
        else:
            #print(f"Directory '{directory_path}' already exists.")
            return False


class Downloader(Base):
    def download_video(self, args) -> tuple:
        video_url, output_path = args
        try:
            yt = YouTube(video_url)
            video_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
            og_filename = video_stream.default_filename.replace('?','').replace('/', '').replace(',','').replace('*','').replace('"','')
            video_stream.download(output_path, filename=og_filename)
            dest_filename = video_stream.title.replace('?','').replace('/', '').replace(',','').replace('*','').replace('"','')
            self.ffmpeg_extract_audio(f"{output_path}/{og_filename}", f"{output_path}/{dest_filename}.mp3")
            return (video_url, True, f"Download successful for {video_stream.title}")
        except Exception as e:
            error_message = f"Error downloading video from {video_url}: {e}"
            return (video_url, False, error_message)

    def download(self, id: list | str, path: str) -> None:
        if isinstance(id, list):
            for i in id:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.set_default_timeout(10000)
                    try:
                        page.goto(f"https://www.youtube.com/playlist?list={i['id']}")
                        thumbnail_links = page.locator('#thumbnail a').all()
                        urlslist  = [f"https://www.youtube.com{link.get_attribute('href')}" for link in thumbnail_links if link.get_attribute('href')]
                        times = page.locator('#text').all()
                        albumElement = page.locator('#text').first
                        albumName = albumElement.text_content().replace('?','').replace('/', '').replace(',','').replace('*','').replace('|', '').replace('"','')
                        timelist = [time_element.inner_text() for time_element in times if time_element.get_attribute('aria-label')]
                        strip_times = [time.strip() for time in timelist]
                        convertTime = lambda time_str: (datetime.strptime(re.sub(r'\s+', ' ', time_str).strip(), "%M:%S") - datetime(1900, 1, 1)).total_seconds()
                        totalTime = [convertTime(times) for times in strip_times if convertTime(times) < 900]
                        urls = [urlslist[index] for index in range(len(totalTime))]
                    except Exception as e:
                        logging.exception(f"An error occurred: {str(e)}")
                    finally:
                        soup = BeautifulSoup(page.content(), 'html.parser')
                        headers = soup.find_all("yt-formatted-string")
                        browser.close()
                        try:
                            meta = [re.split("•|-", i.text) for i in headers if "Album" in i.text]
                            albumName = f"{meta[1][0]} - {meta[0][-1]}"
                        except Exception:
                            pass
                        album_path = f"{path}/{albumName}"
                        self.create_directory(album_path)
                        processes = 10
                        arguments = [(url, album_path) for url in urls]
                        with multiprocessing.Pool(processes=processes) as pool:
                            pool.map(self.download_video, arguments)
                        pool.close()
                        pool.join()
                        for filename in os.listdir(album_path):
                            if not filename.endswith('.mp3'):
                                filepath = os.path.join(album_path, filename)
                                try:
                                    os.remove(filepath)
                                except Exception as e:
                                    pass
        else:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page()
                try:
                    page.goto(f"https://www.youtube.com/playlist?list={id}")
                    thumbnail_links = page.locator('#thumbnail a').all()
                    urlslist  = [f"https://www.youtube.com{link.get_attribute('href')}" for link in thumbnail_links if link.get_attribute('href')]
                    times = page.locator('#text').all()
                    albumElement = page.locator('#text').first
                    albumName = albumElement.text_content().replace('?','').replace('/', '').replace(',','').replace('*','').replace('|', '').replace('"','')
                    timelist = [time_element.inner_text() for time_element in times if time_element.get_attribute('aria-label')]
                    strip_times = [time.strip() for time in timelist]
                    convertTime = lambda time_str: (datetime.strptime(re.sub(r'\s+', ' ', time_str).strip(), "%M:%S") - datetime(1900, 1, 1)).total_seconds()
                    totalTime = [convertTime(times) for times in strip_times if convertTime(times) < 900]
                    urls = [urlslist[index] for index in range(len(totalTime))]
                    page.wait_for_timeout(2500)
                except Exception as e:
                    logging.exception(f"An error occurred: {str(e)}")
                finally:
                    soup = BeautifulSoup(page.content(), 'html.parser')
                    headers = soup.find_all("yt-formatted-string")
                    browser.close()
                    try:
                        meta = [re.split("•|-", i.text) for i in headers if "Album" in i.text]
                        albumName = f"{meta[1][0]} - {meta[0][-1]}"
                    except Exception:
                        pass
                    album_path = f"{path}/{albumName}"
                    self.create_directory(album_path)
                    processes = 10
                    arguments = [(url, album_path) for url in urls]
                    with multiprocessing.Pool(processes=processes) as pool:
                        pool.map(self.download_video, arguments)
                    pool.close()
                    pool.join()
                    for filename in os.listdir(album_path):
                        if not filename.endswith('.mp3'):
                            filepath = os.path.join(album_path, filename)
                            try:
                                os.remove(filepath)
                            except Exception as e:
                                logging.exception(e)


class SingleDownload(Base):
    def download_video(self, video_id: str, output_path: str) -> tuple:
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            yt = YouTube(video_url)
            video_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
            artist = yt.vid_info['videoDetails']['author']
            og_filename = video_stream.default_filename.replace('?','').replace('/', '').replace(',','').replace('*','').replace('"','')
            video_stream.download(output_path, filename=og_filename)
            dest_filename = video_stream.title.replace('?','').replace('/', '').replace(',','').replace('*','').replace('"','')
            self.ffmpeg_extract_audio(f"{output_path}/{og_filename}", f"{output_path}/{artist} - {dest_filename}.mp3")
            return (video_url, True, f"Download successful for {video_stream.title}")
        except Exception as e:
            error_message = f"Error downloading video from {video_url}: {e}"
            return (video_url, False, error_message)

    def download(self, id: list | str, path: str) -> None:
        if isinstance(id, list):
            for i in id:
                album_path = f"{path}/"
                self.create_directory(album_path)
                downloading = self.download_video(i['id'], album_path)
                if downloading:
                    for filename in os.listdir(album_path):
                        if not filename.endswith('.mp3'):
                            filepath = os.path.join(album_path, filename)
                            try:
                                os.remove(filepath)
                            except Exception as e:
                                pass
        else:
            album_path = f"{path}/"
            self.create_directory(album_path)
            downloading = self.download_video(id, album_path)
            if downloading:
                for filename in os.listdir(album_path):
                    if not filename.endswith('.mp3'):
                        filepath = os.path.join(album_path, filename)
                        try:
                            os.remove(filepath)
                        except Exception as e:
                            pass
if __name__ == "__main__":
    playlist_id = str(input('Enter Playlist Id: '))
    downloader = SingleDownload()
    downloader.download(playlist_id, "path")
