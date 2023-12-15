import argparse
import docker
from commands.exec import exec
from commands.images import images
from commands.ps import ps
from commands.run import run
from commands.push import push
from commands.pull import pull
from commands.build import build
from commands.ctop import ctop

COMMANDS = {
    'RUN': 'run',
    'EXEC': 'exec',
    'BUILD': 'build',
    'PUSH': 'push',
    'PULL': 'pull',
    'PS': 'ps',
    'IMAGES': 'images',
    'TOP': 'top'
}


def main():
    try:
        client = docker.from_env()
    except:
        client = None

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    run_parser = subparsers.add_parser(
        COMMANDS['RUN'], help='Create Container')
    push_parser = subparsers.add_parser(
        COMMANDS['PUSH'], help='image push')
    pull_parser = subparsers.add_parser(
        COMMANDS['PULL'], help='image pull')
    exec_parser = subparsers.add_parser(
        COMMANDS['EXEC'], help='Execute a command in a running container')
    build_parser = subparsers.add_parser(
        COMMANDS['BUILD'], help='Build image')
    ps_parser = subparsers.add_parser(
        COMMANDS['PS'], help='List containers')
    images_parser = subparsers.add_parser(
        COMMANDS['IMAGES'], help='List images')
    top_parser=subparsers.add_parser(
        COMMANDS['TOP'], help='show container information')

    args = parser.parse_args()

    if args.command == COMMANDS['RUN']:
        run(client)
    elif args.command == COMMANDS['PUSH']:
        push(client)
    elif args.command == COMMANDS['PULL']:
        pull(client)
    elif args.command == COMMANDS['BUILD']:
        build(client)
    elif args.command == COMMANDS['EXEC']:
        exec(client)
    elif args.command == COMMANDS['PS']:
        ps(client)
    elif args.command == COMMANDS['IMAGES']:
        images(client)
    elif args.command==COMMANDS['TOP']:
        ctop()


if __name__ == '__main__':
    main()
