import threading
from queue import Queue
import os
import requests
import logging
import sys
import json
import base64
import asyncio

from openai import OpenAI


from flask import Flask, request, jsonify

SERVER_ADDRESS = os.environ.get('DAM_SERVER_ADDRESS')
ACCOUNT_KEY = os.environ.get('DAM_ACCOUNT_KEY')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

DEFAULT_SYSTEM_PROMPT = """Look at the thumbnail image of this digital asset as well as any extra information provided such as file name, path, changelist description, and asset type, to create a list of tags for searching and categorizing, as well as a short description of the image so that a user could understand it without seeing the image.

Use your existing knowledge of naming conventions, folder structures, thumbnail generation, and how artists write changelist descriptions when submitting their work. Use your judgement to determine which pieces of information apply to this thumbnail and what tags and description will be most helpful for searchability later on.

Tags should be sorted in order of confidence. Put your best tags at the top. If the user tells you the file type and it is not obvious from the file extension, be sure to include it as a tag. For example, Unreal Engine assets are all .uasset files but they have many different types, like "BlueprintGeneratedClass", "Texture2D", "StaticMesh", "SkeletalMesh", etc. Do not guess about the file type if you are not sure. For example, in image is not necessarily a texture, so don't tag it as such unless you are sure.

The output should be in JSON format with the keys "tags", "description", and "filepath"

Here are some examples:

<output>
{
    "tags": [
        "building",
        "castle",
        "medieval",
        "cartoon",
        "fantasy"
    ],
    "description": "A cartoon style medieval castle with a moat and drawbridge. Mountains are in the background.",
    "filepath": "//depot/art/castle/castle_v001.uasset"
}
</output>

<output>
{
    "tags": [
        "StaticMesh",
        "desk",
        "wooden",
        "executive",
        "office",
    ],
    "description": "A 3D model of a wooden executive desk with large drawers.",
    "filepath": "//depot/art/desk/desk_v002.uasset"
}
</output>

<output>
{
    "tags": [
        "Texture2D",
        "bricks",
        "wall",
        "weathered",
        "damaged",
        "dirty",
        "old"
    ],
    "description": "A weathered and damaged brick wall texture with dirt and grime. The bricks are old and some are missing.",
    "filepath": "//depot/art/brick_wall/brick_wall_v010.uasset" 
}
</output>
"""

client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s - %(levelname)s] %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

app = Flask(__name__)


# Queue for processing tasks
process_queue = Queue()

def get_or_create_metadata_field(field_name):
    metadata_field_url = "{}/api/company/file_attribute_templates".format(SERVER_ADDRESS)
    
    all_metadata_params = {
        'account_key': ACCOUNT_KEY,
    }
        
    all_metadata_response = requests.get(
        metadata_field_url, 
        params=all_metadata_params,
    )

    if all_metadata_response.status_code > 299:
        print('request failed')
        return
    
    all_metadata = all_metadata_response.json()
    
    image_description_field = [_ for _ in all_metadata['results'] if _['name'] == field_name]

    if image_description_field:
        image_description_field = image_description_field[0]
    else:
        add_metadata_field_params = {
            'account_key': ACCOUNT_KEY,
            "name": field_name,
            "type": "text",
            "available_values":[],
            "hidden": False
        }
        
        add_metadata_field_response = requests.post(
            metadata_field_url, 
            json=add_metadata_field_params,
        )

        image_description_field = add_metadata_field_response.json()

    return image_description_field


def get_preview_image(depot_path, changelist=None):
    get_preview_url = "{}/api/p4/files/preview".format(SERVER_ADDRESS)
    
    get_preview_params = {
        'account_key': ACCOUNT_KEY,
        'depot_path': depot_path
    }

    if changelist:
        get_preview_params['identifier'] = changelist

    get_preview_response = requests.get(
        get_preview_url, 
        params=get_preview_params,
    )
    print(get_preview_url)
    print(ACCOUNT_KEY)
    print(get_preview_response)

    if get_preview_response.status_code > 299:
        print('request failed')
        return
    
    return get_preview_response


def attach_metadata(selected_asset, field_name, value):

    image_description_field = get_or_create_metadata_field(field_name)

    add_asset_metadata_url = "{}/api/p4/batch/custom_file_attributes".format(SERVER_ADDRESS)
    
    add_asset_metadata_body = {
        'account_key': ACCOUNT_KEY,
        'paths':[
            {
                'path': selected_asset
            }
        ],
        'create': [
            {
                'uuid': image_description_field['uuid'],
                'value': value
            }
        ]
    }
        
    if '@' in selected_asset:
        asset_path, asset_identifier = selected_asset.split('@')
        add_asset_metadata_body['paths'][0]['path'] = asset_path
        add_asset_metadata_body['paths'][0]['identifier'] = asset_identifier

    add_asset_metadata_response = requests.put(
        add_asset_metadata_url, 
        json=add_asset_metadata_body,
    )

    print(add_asset_metadata_response)
    try:
        print(add_asset_metadata_response.json())
    except:
        print('no metadata json')


def attach_additional_tags(selected_asset, tags):
    if not tags:
        return
    
    add_asset_tags_url = "{}/api/p4/batch/tags".format(SERVER_ADDRESS)
    add_asset_tags_body = {
        'account_key': ACCOUNT_KEY,
        'paths':[
            {
                'path': selected_asset
            }
        ],
        'create': tags,

    }
        
    if '@' in selected_asset:
        asset_path, asset_identifier = selected_asset.split('@')
        add_asset_tags_body['paths'][0]['path'] = asset_path
        add_asset_tags_body['paths'][0]['identifier'] = asset_identifier

    add_asset_tags_response = requests.put(
        add_asset_tags_url, 
        json=add_asset_tags_body,
    )

    print(add_asset_tags_response)
    try:
        print(add_asset_tags_response.json())
    except:
        print('no tags json')


def process_changelist(file_process_dict: dict):
    items = []
    for file in file_process_dict["file_list"]:
        message = json.dumps(
            {
                "filepath": file["depot_path"].split("@")[0],
            }
        )
        items.append(
            {
                "depot_path": file["depot_path"],
                "message": message,
                "b64image": file["preview"],
                "image_type": file["preview_type"],
            }
        )
    output = []

    async def _process_items(items, output):
        tasks = [_invoke_async(item) for item in items]
        results = await asyncio.gather(*tasks)
        output.extend(results)

    asyncio.run(_process_items(items, output))
    return output


async def _invoke_async(item):
    image = base64.b64encode(item['b64image']).decode('utf-8')

    response = client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {
                "role": "system",
                "content": DEFAULT_SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text", 
                        "text": item["message"]
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{item['image_type']};base64,{image}"}                    
                    }
                ]
            }
        ],
        max_completion_tokens=300,
    )
    return response


def process_file(depot_path: str) -> None:
    image_response = get_preview_image(depot_path)
    file_process_dict = {
        "file_list": [
            {
                "depot_path": depot_path,
                "preview": image_response.content,
                "preview_type": image_response.headers.get('content-type')
            },
        ],
    }

    ai_results = process_changelist(file_process_dict)

    for result in ai_results:
        data_dict = json.loads(result.choices[0].message.content)
        attach_metadata(
            data_dict["filepath"], "image description", data_dict["description"]
        )
        attach_additional_tags(data_dict["filepath"], data_dict["tags"])

    logger.info(ai_results)
    return ai_results


def worker():
    while True:
        depot_path = process_queue.get()
        process_file(depot_path)
        process_queue.task_done()


# Start worker thread
threading.Thread(target=worker, daemon=True).start()


@app.route("/webhook", methods=["POST"])
def webhook():
    logging.debug(f"Received webhook request. {request}")
    print('request.json',request.json)
    data = request.json
    if not data:
        logging.error("No JSON data in request")
        return jsonify({"error": "No JSON data in request"}), 400

    new_files = []

    for update in data:
        if (
            "objects" not in update
            or "files" not in update["objects"]
            or (
                "added" not in update["objects"]["files"]
                and "modified" not in update["objects"]["files"]
            )
        ):
            logging.warning(
                "Skipping update: No added or modified 'objects' or 'files' in update"
            )
            logging.debug(str(update))
            continue

        for action in ["added", "modified"]:
            for file in update["objects"]["files"][action]:
                    new_files.append(file)

    for depot_path in new_files:
        process_queue.put(depot_path)

    return jsonify({"message": f"Queued {len(new_files)} files for processing"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8800, debug=False)
