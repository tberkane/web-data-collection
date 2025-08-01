GENERATE_QUERIES_PROMPT = """
You are a helpful assistant that generates search queries. Focus on creating concise queries that will find individual data points or small pieces of information, NOT complete datasets or comprehensive lists. Each query should aim to find pages that contain just one or a few relevant pieces of information. Make sure to include important keywords from the dataset description in the query. Each query should be extremely short and straightforward and the first thing you think of. Do not try to be creative but instead mostly reuse words from the dataset description. Return ONLY a JSON array of query strings. Do not include any explanation or additional text.

Generate {num_queries} Google Search queries for the following dataset description:
{dataset_description}"""

GENERATE_QUERIES_WITH_VARIABLES_PROMPT = """
You are a helpful assistant that generates search query templates. Focus on creating concise templates that will find individual data points or small pieces of information, NOT complete datasets or comprehensive lists. Each template should aim to find pages that contain just one or a few relevant pieces of information. Make sure to include important keywords from the dataset description in the template. Each template should be extremely short and straightforward and the first thing you think of. Do not try to be creative but instead mostly reuse words from the dataset description. The templates MUST contain ALL the following placeholder variables, surrounded by curly braces: {variable_names}. Return ONLY a JSON array of template strings. Do not include any explanation or additional text.

Generate {num_queries} Google Search queries for the following dataset description:
{dataset_description}"""

GENERATE_EXTRACTION_SCHEMA_PROMPT = """Generate a Pydantic schema based on a list of fields
and a dataset description.

Guidelines:
1. Create one field for each item mentioned in the
list of fields and data description.
2. Pick an appropriate data type for each field: int,
str or bool. No other types are allowed.
3. Include a description for each field.
4. If there is a date field, use the format YYYY-MM-DD.

The schema should be in the following format:
"'python
class DataModel(BaseModel):
field_name: data_type = Field(..., description="Description of the field")
# Add more fields as necessary
"'

Example:
For the list of fields "country", "date" and data
description "Number of cholera cases", the output
should be:
"'python
class CholeraCases(BaseModel):
country: str = Field(..., description="Name of the
country for which the cholera case count is reported")
date: str = Field(..., description="Date for which the
cholera case count is reported in YYYY-MM-DD
format")
cholera_cases: int = Field(..., description="Number
of reported cholera cases")
"'

Please generate the Pydantic schema for the given
list of fields: {schema_fields} and dataset description:
{dataset_description}.

Return ONLY the schema. Do not include any explanation or additional text. DO NOT enclose the schema with ```python or ``` or anything else."""

QUALITY_CONTROL_PROMPT = """Below is a dataset collected by an LLM from the web from the prompt:
{dataset_description}

{extracted_data}

Your task is to examine each row and sanity check it, finding as many potential problems with it as possible and making sure it is consistent with the rest of the data. Output EXACTLY one line per ID. Do not miss any rows, do not output any extra rows and do not combine multiple rows' issues. Please always refer to the data points by their ID.

Format your response as follows:
{{ID number}}: sentence describing potential problems with the row corresponding to the ID, or output only "NA" if you find no issues in a row.
"""
