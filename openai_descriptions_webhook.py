import threading
from queue import Queue
import logging
import sys
import json

import environment as environment

from dam_api.write_metadata import attach_metadata, attach_additional_tags, get_preview_image
import tagging_ai

from flask import Flask, request, jsonify


logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s - %(levelname)s] %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

app = Flask(__name__)


# Queue for processing tasks
process_queue = Queue()


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

    ai_results = tagging_ai.process_changelist(file_process_dict)

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
