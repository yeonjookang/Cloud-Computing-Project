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


def get_container_stats(container):
    created = format_time(container.attrs['Created'])
    status = container.status
    ports = container.attrs['NetworkSettings']['Ports']
    image = container.image.tags[0] if container.image.tags else container.image.id

    stats = container.stats(stream=False)
    memory_usage = format_size(stats['memory_stats']['usage'])

    return {
        "ID": container.short_id,
        "Name": container.name,
        "Created": created,
        "Status": status,
        "Ports": ports,
        "Image": image,
        "Memory Usage": memory_usage
    }


def ps(client: DockerClient | None):
    try:
        if client is None:
            raise ValueError("Docker client is not initialized.")

        questions = [
            {
                'type': 'confirm',
                'name': 'all',
                'message': 'Show all containers?',
                'default': False
            },
            {
                'type': 'input',
                'name': 'since',
                'message': 'Show only containers created since Id or Name (leave blank for none):',
            },
            {
                'type': 'input',
                'name': 'before',
                'message': 'Show only containers created before Id or Name (leave blank for none):',
            },
            {
                'type': 'input',
                'name': 'limit',
                'message': 'Limit the number of containers to show (leave blank for no limit):',
            },
            {
                'type': 'input',
                'name': 'filters',
                'message': 'Enter any filters in JSON format (leave blank for none):',
            },
            {
                'type': 'confirm',
                'name': 'sparse',
                'message': 'Do not inspect containers?',
                'default': False
            },
            {
                'type': 'confirm',
                'name': 'ignore_removed',
                'message': 'Ignore failures due to missing containers?',
                'default': False
            },
        ]

        answers = prompt(questions)

        filters = {}
        if answers['since']:
            filters['since'] = answers['since']
        if answers['before']:
            filters['before'] = answers['before']
        if answers['filters']:
            filters.update(json.loads(answers['filters']))

        containers = client.containers.list(
            all=answers['all'], filters=filters)

        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID")
        table.add_column("Name")
        table.add_column("Created")
        table.add_column("Status")
        table.add_column("Ports")
        table.add_column("Image")
        table.add_column("Memory Usage")

        with concurrent.futures.ThreadPoolExecutor() as executor:
            for container_info in executor.map(get_container_stats, containers):
                table.add_row(
                    container_info["ID"],
                    container_info["Name"],
                    container_info["Created"],
                    container_info["Status"],
                    str(container_info["Ports"]),
                    container_info["Image"],
                    container_info["Memory Usage"]
                )

        console.print(table)

    except Exception as e:
        print('예외가 발생했습니다.', e)
