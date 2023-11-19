from __future__ import print_function, unicode_literals
from PyInquirer import prompt, print_json
from docker import DockerClient
import docker

def pull(client: DockerClient | None):
    questions = [
        {
            'type': 'input',
            'name': 'repository',
            'message': 'Enter the image name you want to pull:',
            'default': ''
        },
        {
            'type': 'input',
            'name': 'tag',
            'message': 'Enter the tag name of the image you want to pull:',
            'default': 'latest'
        }
    ]

    answers = prompt(questions)

    try:
        pull = client.images.pull(
            repository=answers['repository'],
            tag=answers['tag']
        )
        print(pull)
    except Exception as e:
        print(f"API error: {e}")
