import logging
import argparse
import json
import environment as environment

from dam_api.write_metadata import attach_metadata, attach_additional_tags, get_preview_image
import tagging_ai


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def main(depot_path, changelist):
    image_response = get_preview_image(depot_path, changelist)
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("depot_path")
    parser.add_argument("changelist")

    parsed_args = parser.parse_args()
    main(parsed_args.depot_path, parsed_args.changelist)
