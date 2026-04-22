import os
import base64
import asyncio
import json
import logging

from openai import OpenAI

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

client = OpenAI(api_key=OPENAI_API_KEY)

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