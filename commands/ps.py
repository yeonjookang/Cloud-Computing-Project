from __future__ import print_function, unicode_literals
import json
from PyInquirer import prompt
from docker import DockerClient
import concurrent.futures


def get_container_stats(container):
    created = container.attrs['Created']
    status = container.status
    ports = container.attrs['NetworkSettings']['Ports']
    image = container.image.tags[0] if container.image.tags else container.image.id
    command = container.attrs['Config']['Cmd']
    env = container.attrs['Config']['Env']
    volumes = container.attrs['Mounts']
    networks = container.attrs['NetworkSettings']['Networks']

    stats = container.stats(stream=False)
    memory_usage = stats['memory_stats']['usage']

    return f"ID: {container.id}, Name: {container.name}, Created: {created}, Status: {status}, Ports: {ports}, Image: {image},  Memory Usage: {memory_usage}"


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

        with concurrent.futures.ThreadPoolExecutor() as executor:
            for container_info in executor.map(get_container_stats, containers):
                print(container_info)

    except Exception as e:
        print('예외가 발생했습니다.', e)
