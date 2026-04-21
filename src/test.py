import base64
from openai import OpenAI


DEFAULT_SYSTEM_PROMPT = """Look at the thumbnail image of this digital asset as well as any extra information provided such as file name, path, changelist description, and asset type, to create a list of tags for searching and categorizing, as well as a short description of the image so that a user could understand it without seeing the image.

Use your existing knowledge of naming conventions, folder structures, thumbnail generation, and how artists write changelist descriptions when submitting their work. Use your judgement to determine which pieces of information apply to this thumbnail and what tags and description will be most helpful for searchability later on.

Tags should be sorted in order of confidence. Put your best tags at the top. If the user tells you the file type and it is not obvious from the file extension, be sure to include it as a tag. For example, Unreal Engine assets are all .uasset files but they have many different types, like "BlueprintGeneratedClass", "Texture2D", "StaticMesh", "SkeletalMesh", etc. Do not guess about the file type if you are not sure. For example, in image is not necessarily a texture, so don't tag it as such unless you are sure.

The output should be in JSON format with the keys "tags" and "description"

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
    "description": "A cartoon style medieval castle with a moat and drawbridge. Mountains are in the background."
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
    "description": "A 3D model of a wooden executive desk with large drawers."
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
    "description": "A weathered and damaged brick wall texture with dirt and grime. The bricks are old and some are missing."
}
</output>
"""

def open_ai_tag_test(image_path):
    # 1. Initialize the client
    client = OpenAI(api_key="")

    # 2. Function to encode the image
    def encode_image(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    # Path to your image and additional context
    base64_image = encode_image(image_path)

    # 3. Define the context and call the API
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
                        "text": ""
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            }
        ],
        max_completion_tokens=300,
    )

    print(response.choices[0].message.content)

if __name__ == "__main__":
    open_ai_tag_test(r"E:\repos\p4dam_descriptions_openai\test_images\heo-ilhaeng-26.jpg")
