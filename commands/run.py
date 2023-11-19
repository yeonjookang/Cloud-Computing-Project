from __future__ import print_function, unicode_literals
from PyInquirer import prompt, print_json
from docker import DockerClient
import docker


def run(client: DockerClient | None):
    questions = [
        {
            'type': 'confirm',
            'name': 'detached',
            'message': 'Do you want to run the container in detached mode?',
            'default': False
        },
        {
            'type': 'confirm',
            'name': 'interactive',
            'message': 'Do you want to run the container in interactive mode with a pseudo-TTY?',
            'default': False
        },
        {
            'type': 'input',
            'name': 'name',
            'message': 'Enter a name for your container (leave blank for none):',
            'default': ''
        },
        {
            'type': 'input',
            'name': 'environment',
            'message': 'Enter any environment variables (format: VAR=value, separate multiple with a comma):',
            'default': ''
        },
        {
            'type': 'input',
            'name': 'port_mapping',
            'message': 'Enter port mappings (format: host_port:container_port, separate multiple with a comma):',
            'default': ''
        },
        {
            'type': 'input',
            'name': 'volume',
            'message': 'Enter volume mappings (format: host_path:container_path, separate multiple with a comma):',
            'default': ''
        },
        {
            'type': 'input',
            'name': 'working_directory',
            'message': 'Enter the working directory inside the container:',
            'default': ''
        },
        {
            'type': 'input',
            'name': 'entrypoint',
            'message': 'Enter the entrypoint command (leave blank for default):',
            'default': ''
        },
        {
            'type': 'confirm',
            'name': 'remove',
            'message': 'Should the container be automatically removed on exit?',
            'default': False
        },
        {
            'type': 'input',
            'name': 'image',
            'message': 'Enter the Docker image to use:',
            'validate': lambda val: val != '',
            'filter': lambda val: val.strip()
        },
        {
            'type': 'input',
            'name': 'command',
            'message': 'Enter any command to run in the container (leave blank for default):',
            'default': ''
        }
    ]

    answers = prompt(questions)

    try:
        container = client.containers.run(
            image=answers['image'],
            command=answers['command'],
            detach=True
        )
        print(container.logs())
        container.stop()
        container.remove()
    except:
        print(f"API error")
