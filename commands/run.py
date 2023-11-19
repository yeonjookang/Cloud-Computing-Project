from __future__ import print_function, unicode_literals
from PyInquirer import prompt, print_json
from docker import DockerClient
import docker


def run(client: DockerClient | None):
    questions = [
        {
            'type': 'input',
            'name': 'image',  # image
            'message': 'Enter the Docker image to use:',
            'validate': lambda val: val != '',
            'filter': lambda val: val.strip()
        },
        {
            'type': 'input',
            'name': 'command',  # command
            'message': 'Enter any command to run in the container (leave blank for default):',
            'default': ''
        },
        {
            'type': 'input',
            'name': 'name',  # name
            'message': 'Enter a name for your container (leave blank for none):',
            'default': ''
        },
        {
            'type': 'confirm',
            'name': 'detached',  # detach
            'message': 'Do you want to run the container in detached mode?',
            'default': False
        },
        {
            'type': 'input',
            'name': 'environment',  # environment -> ["SOMEVARIABLE=xxx"].
            'message': 'Enter any environment variables (format: VAR=value, separate multiple with a comma):',
            'default': ''
        },
        {
            'type': 'input',
            'name': 'port_mapping',  # ports 2222:3333 to { '2222': '3333' }
            'message': 'Enter port mappings (format: host_port:container_port, separate multiple with a comma):',
            'default': ''
        },
        {
            'type': 'confirm',
            'name': 'interactive',  # tty
            'message': 'Do you want to run the container in interactive mode with a pseudo-TTY?',
            'default': False
        },
        {
            'type': 'input',
            'name': 'volume',  # volumes
            'message': 'Enter volume mappings (format: host_path:container_path, separate multiple with a comma):',
            'default': ''
        },
        {
            'type': 'input',
            'name': 'working_directory',  # working_dir
            'message': 'Enter the working directory inside the container:',
            'default': ''
        },
        {
            'type': 'input',
            'name': 'entrypoint',  # entrypoint
            'message': 'Enter the entrypoint command (leave blank for default):',
            'default': ''
        },
        {
            'type': 'confirm',
            'name': 'remove',  # remove
            'message': 'Should the container be automatically removed on exit?',
            'default': False
        },

    ]

    answers = prompt(questions)

    try:
        container = client.containers.run(
            image=answers['image'],
            command=answers['command'],
            name=answers['name'],
            detach=answers['detached'],
            environment=answers['environment'].split(',') if len(
                answers['environment']) > 1 else answers['environment'],
            ports={k: v for k, v in (pair.split(':') for pair in answers['port_mapping'].replace(
                ' ', '').split(',') if ':' in pair)} if answers['port_mapping'] else {},
            tty=answers['interactive'],
            volumes=answers['volume'],
            working_dir=answers['working_directory'],
            entrypoint=answers['entrypoint'],
            remove=answers['remove'],
        )
    except Exception as e:
        print('예외가 발생했습니다.', e)
