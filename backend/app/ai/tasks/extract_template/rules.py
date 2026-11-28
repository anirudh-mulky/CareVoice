from app.ai.tasks.extract_template.schema import ExtractTemplateInput, Template
from app.rules.extractors import extract_template


def run(data: ExtractTemplateInput) -> Template:
    return extract_template(data)
