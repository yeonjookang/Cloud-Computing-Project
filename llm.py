import json
from openai import OpenAI
API_KEY = "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"
client = OpenAI(api_key=API_KEY)


def generate_options(docker_image):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system",
                "content": "You are a helpful assistant designed to output JSON."},
            {"role": "system",
             "content": 'You are an AI assistant who recommend the option values of the docker run command. You can deduce the option values for the docker run command. Options for run command is [command: command to run in the container, name: name for your container, detached: run the container in detached mode, environment: environment variables, port_mapping: Enter port mappings (format: host_port:container_port, separate multiple with a comma), interactive: run the container in interactive mode with a pseudo-TTY, volume:  volume mappings (format: host_path:container_path, separate multiple with a comma), working_directory: working directory inside the container, entrypoint: entrypoint command, remove: Should the container be automatically removed on exit]. If I Give you the name of docker image, give me the expected command for a given docker image in array form. It does not have to be accurate in the option reasoning, so I would like you to suggest the option value as much as possible without emptying the option'},
            {"role": "user", "content": docker_image},
        ]
    )
    return json.loads(response.choices[0].message.content)
