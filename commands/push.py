from __future__ import print_function, unicode_literals
from PyInquirer import prompt, print_json
from docker import DockerClient
import docker

def push(client: DockerClient | None):
    questions = [
        {
            'type': 'input',
            'name': 'repository',
            'message': 'Enter the repository you want to upload the docker image:',
            'default': ''
        },
        {
            'type': 'input',
            'name': 'tag',
            'message': 'Enter the tag name of the image you want to upload:',
            'default': ''
        }
    ]

    answers = prompt(questions)

    try:
        push = client.images.push(
            repository=answers['repository'],
            tag=answers['tag']
        )
        print(push)
    except Exception as e:
        print(f"API error: {e}")
