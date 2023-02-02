import os
import re
import json
import openai
import asyncio
import discord
from discord import Intents
from discord.ext import commands

intents = Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix="!", intents=intents)
c = CamelCase()

with open("keys.json") as f:
    config = json.load(f)

# Set the environment variables
for key, value in config.items():
    os.environ[key] = str(value)

# Access the environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_ORG = os.getenv("OPENAI_ORG")
OPENAI_KEY = os.getenv("OPENAI_KEY")

#define a function to determine if the message is directed at the bot or not using a text completion to determine it, and if not to ignore the message
async def determine_if_directed(message, name, persona_attributes):
    #get the most recent messages in the channel to use as a prompt and join the messages together
    recent_messages = await get_recent_messages(message.channel, 4)
    #add the timestamp to the message
    joined_messages = '\n'.join([f"{m.author}: {m.content}" for m in recent_messages])
    recent_messages = re.sub("ChatGPT Bot#" + persona_attributes["BOTID"], name, joined_messages)
    #create the prompt for openai
    prompt_text=f"""Return True if {message.author} is talking to {name} or false if it is someone else in the chat based on the context of the following messages. If it is only {name} and {message.author}, then default to True. Assume its true unless its obviously false (True/False only). 
###
{recent_messages}
###
answer: """
    response, prompt = create_completion(OPENAI_ORG, OPENAI_KEY, prompt_text)
    print(prompt)
    response = response.strip()
    print(response)
    if response == "True":
        is_directed = True
    else:
        is_directed = False
    return is_directed

#define a function get the name of the channel the message was sent in and capitalize it
def get_channel_name(message):
    channel_name = message.channel.name.capitalize()
    print(channel_name)
    return channel_name

#define a function that determines if the channel_name is a persona or not
def determine_persona(channel_name):
    personas = read_personas()
    is_persona = False
    for persona in personas:
        if channel_name == persona["CHANNEL"]:
            is_persona = True
    print(is_persona)
    return is_persona

#define a function that reads personas.json and returns a dictionary of attributes
def read_personas():
    with open("personas.json") as j:
        personas = json.load(j)
    return personas

#define a function that gets the most recent messages in the channel and returns them as a list
async def get_recent_messages(channel, limit):
    messages = []
    async for message in channel.history(limit=limit):
        messages.insert(0, message)
    return messages

#define a function that creates a dictionary of persona attributes for the channel_name from the personas.json file
def get_persona_attributes(channel_name):
    personas = read_personas()
    for persona in personas:
        if channel_name == persona["CHANNEL"]:
            persona_attributes = persona
    print(persona_attributes)
    return persona_attributes

#define a function that compiles a prompt for openai from the create completion function
def create_persona_prompt(user, user_message, channel_name, joined_messages, persona):
    name = persona["CHANNEL"]
    accent = persona["ACCENT"]
    recent_messages = re.sub("ChatGPT Bot#" + persona["BOTID"], name, joined_messages)
    prompt_text=f"""Meet {name}, who is {accent}.
{persona['DESCRIPTION']}
{persona['START_TEXT']}
{recent_messages}
{name}: """
    return prompt_text

#define a function that connects to openai with the openai org and key to get a completion from davinci
def create_completion(openai_org, openai_key, prompt_text):
    openai.api_key = openai_key
    openai.organization = openai_org
    with open('completionconfig.json') as k:
        config = json.load(k)
    response = openai.Completion.create(
        engine=config['engine'],
        prompt=prompt_text,
        temperature=config['temperature'],
        max_tokens=config['max_tokens'],
        stop=config['stop']
    )
    response_text = response["choices"][0]["text"]
    print(response)
    return response_text, prompt_text

#define an event that listens for a message and sends it to openai to generate a response
@client.event
async def on_message(message):
    try:
        #if the message is not from the bot, send it to openai to generate a response
        if message.author != client.user:
            user = message.author
            user_message = message.content
            channel_name = get_channel_name(message)
            is_persona = determine_persona(channel_name)
            if is_persona == True:
                persona_attributes = get_persona_attributes(channel_name)
                #determine if the message is directed at the bot or not
                is_directed = await determine_if_directed(message, channel_name, persona_attributes)
                if is_directed == False:
                    print(f"Message is not directed at {channel_name}.")
                    return
                #get the most recent messages in the channel to use as a prompt and join the messages together
                recent_messages = await get_recent_messages(message.channel, 10)
                joined_messages = '\n'.join([f"{m.author}: {m.content}" for m in recent_messages])

                #create the prompt for openai
                prompt = create_persona_prompt(user, user_message, channel_name, joined_messages, persona_attributes)
                #get the response from openai
                response, prompt = create_completion(OPENAI_ORG, OPENAI_KEY, prompt)
                print(prompt + response)
            else:
                response = "This channel is not a persona channel."
                print(response)
            await message.channel.send(response)
    except Exception as e:
        print(e)

#create main statement
if __name__ == "__main__":
    #connect to discord
    client.run(DISCORD_TOKEN)
