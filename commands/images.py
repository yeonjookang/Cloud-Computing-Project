from __future__ import print_function, unicode_literals
from PyInquirer import prompt
from docker import DockerClient
from rich.table import Table
from rich.console import Console
from dateutil.parser import parse
from datetime import datetime, timezone
import concurrent.futures
import json


def format_time(time_str):
    time = parse(time_str)
    now = datetime.now(timezone.utc)
    diff = now - time

    seconds = diff.total_seconds()
    if seconds < 60:
        return f"{seconds:.0f} seconds ago"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.0f} minutes ago"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.0f} hours ago"
    days = hours / 24
    return f"{days:.0f} days ago"


def format_size(size):
    # size is in bytes
    size_kb = size / 1024
    if size_kb < 1024:
        return f"{size_kb:.2f}KB"
    size_mb = size_kb / 1024
    if size_mb < 1024:
        return f"{size_mb:.2f}MB"
    size_gb = size_mb / 1024
    return f"{size_gb:.2f}GB"


def get_image_info(image):
    created = format_time(image.attrs['Created'])
    size = format_size(image.attrs['Size'])
    tags = ', '.join(image.tags)

    return {
        "ID": image.short_id,
        "Created": created,
        "Size": size,
        "Tags": tags
    }


def images(client: DockerClient | None):
    try:
        images = client.images.list()

        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID")
        table.add_column("Created")
        table.add_column("Size")
        table.add_column("Tags")

        for image_info in map(get_image_info, images):
            table.add_row(
                image_info["ID"],
                image_info["Created"],
                image_info["Size"],
                image_info["Tags"]
            )

        console.print(table)

    except Exception as e:
        print('예외가 발생했습니다.', e)
