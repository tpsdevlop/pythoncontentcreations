import json
import uuid
import time
import re
import os
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from mimetypes import guess_type
from django.views.decorators.http import require_http_methods
from azure.storage.blob import BlobServiceClient, ContentSettings
from django.template import Template, Context

# Create a BlobServiceClient
blob_service_client = BlobServiceClient(account_url=f"https://{settings.AZURE_ACCOUNT_NAME}.blob.core.windows.net", credential=settings.AZURE_ACCOUNT_KEY)

# Get a reference to the container
container_client = blob_service_client.get_container_client(settings.AZURE_CONTAINER)

@require_POST
@csrf_exempt
def save_data(request):
    try:
        data = json.loads(request.body)

        # Check if the required fields are present
        if not isinstance(data, list) or any(
            'SyllabusName' not in item or 
            'Subject' not in item or 
            'Sections' not in item for item in data
        ):
            return JsonResponse({'error': 'Invalid data format'}, status=400)

        # Iterate through each subject's data and save it into separate blobs
        for item in data:
            syllabus_name = item.get('SyllabusName')
            subject_name = item.get('Subject')
            blob_name = f"{settings.MCQ_FOLDER}{syllabus_name}_{subject_name}.json"

            # Create a blob client using the blob name
            blob_client = container_client.get_blob_client(blob_name)

            # Upload the JSON data to the blob
            blob_client.upload_blob(json.dumps(item, indent=2), overwrite=True)

        return JsonResponse({'message': 'Data saved successfully'}, status=200)

    except json.JSONDecodeError as e:
        return JsonResponse({'error': 'Invalid JSON format in request body'}, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_GET
@csrf_exempt
def load_data(request):
    try:
        data = []
        # List all blobs in the MCQ folder
        blob_list = container_client.list_blobs(name_starts_with=settings.MCQ_FOLDER)

        # Regular expression to match the expected file name pattern
        file_pattern = re.compile(r'^[^_]+_[^_]+\.json$')

        for blob in blob_list:
            # Check if the blob name matches our expected pattern
            if file_pattern.match(blob.name.split('/')[-1]):
                blob_client = container_client.get_blob_client(blob.name)

                try:
                    # Download the blob content
                    blob_content = blob_client.download_blob().readall()

                    # Decode the content (assuming it's UTF-8 encoded)
                    decoded_content = blob_content.decode('utf-8')

                    # Check if the content is not empty
                    if decoded_content.strip():
                        # Parse the JSON content
                        file_data = json.loads(decoded_content)
                        
                        # Check if the JSON has the expected structure
                        if all(key in file_data for key in ['SyllabusName', 'Subject', 'Sections']):
                            data.append(file_data)
                        else:
                            print(f"Warning: Unexpected JSON structure in blob {blob.name}")
                    else:
                        print(f"Warning: Empty content in blob {blob.name}")
                except json.JSONDecodeError as json_error:
                    print(f"JSON Decode Error in blob {blob.name}: {str(json_error)}")
                    print(f"Content: {decoded_content[:100]}...")  # Print first 100 chars for debugging
                except Exception as blob_error:
                    print(f"Error processing blob {blob.name}: {str(blob_error)}")

        if not data:
            return JsonResponse({'message': 'No valid data found'}, status=404)

        return JsonResponse(data, safe=False)

    except Exception as e:
        return JsonResponse({'error': f"An unexpected error occurred: {str(e)}"}, status=500)

@csrf_exempt
def save_json(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        selected_concept = data.get('selectedConcept')
        selected_name = data.get('selectedName')
        forms = data.get('forms')

        json_data = {
            "concept": selected_concept,
            "details": []
        }

        for index, form in enumerate(forms, start=1):
            detail = {
                "_name": selected_name if selected_name else "",
                "_type": form['selectedType'].lower(),
                "_path": "",
            }

            if form['option'] == 'upload' and 'filePath' in form:
                # For uploaded files, we'll need to handle file upload separately
                detail["_path"] = form['filePath']
            elif form['option'] == 'link':
                detail["_path"] = form['link']
            elif form['option'] == 'text':
                # For text content, we'll save it to a blob and store the path
                content_filename = f'{uuid.uuid4()}.txt'
                blob_name = f"{settings.MCQ_FOLDER}{content_filename}"
                blob_client = container_client.get_blob_client(blob_name)
                blob_client.upload_blob(form['editorContent'], overwrite=True)
                detail["_path"] = blob_name

            detail["_page"] = f"Page{index}"

            json_data["details"].append(detail)

        # Determine the JSON file name
        if selected_concept:
            json_file_name = f'{selected_concept}.json'
        else:
            # Find the next available Q file name
            existing_files = container_client.list_blobs(name_starts_with=settings.MCQ_FOLDER)
            q_files = [blob.name for blob in existing_files if re.match(r'^Q\d+\.json$', blob.name.split('/')[-1])]
            q_numbers = sorted([int(re.match(r'^Q(\d+)\.json$', q_file.split('/')[-1]).group(1)) for q_file in q_files])
            next_q_number = q_numbers[-1] + 1 if q_numbers else 1
            json_file_name = f'Q{next_q_number}.json'

        blob_name = f"{settings.MCQ_FOLDER}{json_file_name}"
        
        # Create a blob client using the blob name
        blob_client = container_client.get_blob_client(blob_name)

        # Upload the JSON data to the blob
        blob_client.upload_blob(json.dumps(json_data, indent=4), overwrite=True)

        return JsonResponse({'message': 'JSON file saved successfully!', 'filename': json_file_name}, status=201)

    return JsonResponse({'error': 'Invalid request method'}, status=400)


@csrf_exempt
def upload_file(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file_obj = request.FILES['file']
        file_extension = os.path.splitext(file_obj.name)[1]
        unique_filename = f'{uuid.uuid4()}{file_extension}'
        blob_name = f"{settings.MCQ_FOLDER}{unique_filename}"

        # Create a blob client using the blob name
        blob_client = container_client.get_blob_client(blob_name)

        # Upload the file content to the blob
        blob_client.upload_blob(file_obj.read(), overwrite=True)

        mime_type, _ = guess_type(blob_name)
        
        return JsonResponse({'filePath': blob_name, 'mimeType': mime_type}, status=201)

    return JsonResponse({'error': 'Invalid request method or no file provided'}, status=400)

def get_dropdown_data(request):
    # Get the selected values from the request parameters
    selected_syllabus = request.GET.get('syllabus', '')
    selected_subject = request.GET.get('subject', '')
    selected_section = request.GET.get('section', '')
    selected_subsection = request.GET.get('subsection', '')

    # Initialize data structures
    all_data = {
        'syllabus': set(),
        'subject': set(),
        'sections': set(),
        'subsections': set(),
        'concepts': set(),
        'names': set()
    }
    
    try:
        # List all blobs in the MCQ folder
        blob_list = container_client.list_blobs(name_starts_with=settings.MCQ_FOLDER)

        # Regular expression to match the expected file name pattern
        file_pattern = re.compile(r'^[^_]+_[^_]+\.json$')

        # Process each JSON blob
        for blob in blob_list:
            # Check if the blob name matches our expected pattern
            if file_pattern.match(blob.name.split('/')[-1]):
                # Get a blob client for the blob
                blob_client = container_client.get_blob_client(blob.name)

                try:
                    # Download the blob content
                    blob_content = blob_client.download_blob().readall()

                    # Decode the content (assuming it's UTF-8 encoded)
                    decoded_content = blob_content.decode('utf-8')

                    # Check if the content is not empty
                    if decoded_content.strip():
                        # Parse the JSON content
                        data = json.loads(decoded_content)
                        
                        # Check if the JSON has the expected structure
                        if all(key in data for key in ['SyllabusName', 'Subject', 'Sections']):
                            syllabus_name = data.get('SyllabusName', 'Unknown Syllabus')
                            all_data['syllabus'].add(syllabus_name)

                            # Filter based on selected syllabus
                            if not selected_syllabus or selected_syllabus == syllabus_name:
                                subject = data.get('Subject', 'Unknown Subject')
                                all_data['subject'].add(subject)

                                # Filter based on selected subject
                                if not selected_subject or selected_subject == subject:
                                    for section in data.get('Sections', []):
                                        section_name = section.get('Name', '')
                                        all_data['sections'].add(section_name)

                                        # Filter based on selected section
                                        if not selected_section or selected_section == section_name:
                                            for subsection in section.get('Subsections', []):
                                                subsection_name = subsection.get('Name', '')
                                                all_data['subsections'].add(subsection_name)

                                                # Filter based on selected subsection
                                                if not selected_subsection or selected_subsection == subsection_name:
                                                    for chapter in subsection.get('Chapters', []):
                                                        all_data['concepts'].add(chapter.get('Concept', ''))
                                                        all_data['names'].add(chapter.get('Name', ''))
                        else:
                            print(f"Warning: Unexpected JSON structure in blob {blob.name}")
                    else:
                        print(f"Warning: Empty content in blob {blob.name}")
                except json.JSONDecodeError as json_error:
                    print(f"JSON Decode Error in blob {blob.name}: {str(json_error)}")
                    print(f"Content: {decoded_content[:100]}...")  # Print first 100 chars for debugging
                except Exception as blob_error:
                    print(f"Error processing blob {blob.name}: {str(blob_error)}")

        # Types remain the same for all files
        types = [
            'Text', 'PDF', 'Word', 'Excel', 'PowerPoint',
            'Image', 'Video', 'Audio',
            'HTML', 'Markdown', 'Code',
            'CSV', 'JSON', 'XML',
            'Other'
        ]

        response_data = {
            'syllabus': list(all_data['syllabus']),
            'subject': list(all_data['subject']),
            'sections': list(all_data['sections']),
            'subsections': list(all_data['subsections']),
            'concepts': list(all_data['concepts']),
            'names': list(all_data['names']),
            'types': types
        }

        return JsonResponse(response_data, status=200)

    except Exception as e:
        return JsonResponse({'error': f"An unexpected error occurred: {str(e)}"}, status=500)
    
def get_templates_from_blob():
    try:
        templates = []
        # List all blobs in the MCQ/templates folder
        blob_list = container_client.list_blobs(name_starts_with=f"{settings.MCQ_FOLDER}templates/")

        for blob in blob_list:
            filename = blob.name.split('/')[-1]
            if filename.endswith('.html') or filename.endswith('.js'):
                templates.append({
                    'name': filename[:-5] if filename.endswith('.html') else filename[:-3],
                    'type': 'html' if filename.endswith('.html') else 'js'
                })

        return templates

    except Exception as e:
        print(f"An error occurred while retrieving templates: {str(e)}")
        return []

@method_decorator(csrf_exempt, name='dispatch')
class TemplatesView(View):
    def get(self, request):
        templates = get_templates_from_blob()
        return JsonResponse({"templates": templates})

@method_decorator(csrf_exempt, name='dispatch')
class RenderTemplateView(View):
    def get(self, request, template_name):
        question_id = request.GET.get('question_id')
        if not question_id:
            return JsonResponse({"error": "Question ID is required"}, status=400)

        try:
            # Load the question data from BLOB
            question_blob_client = container_client.get_blob_client(f"{settings.MCQ_FOLDER}{question_id}")
            question_data = json.loads(question_blob_client.download_blob().readall().decode('utf-8'))

            # Load the template from BLOB
            template_blob_client = container_client.get_blob_client(f"{settings.MCQ_FOLDER}templates/{template_name}.html")
            template_content = template_blob_client.download_blob().readall().decode('utf-8')

            # Render the template with the question data
            template = Template(template_content)
            context = Context(question_data)
            rendered_template = template.render(context)

            return JsonResponse({"rendered_template": rendered_template})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class QuestionView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            question_type = data.get('type', 'unknown')
            
            # Transform the data based on question type
            transformed_data = self.transform_data(data)
            
            # Generate a unique filename
            filename = f"{question_type}_{int(time.time())}.json"
            blob_name = f"{settings.MCQ_FOLDER}{filename}"
            
            # Create a blob client
            blob_client = container_client.get_blob_client(blob_name)
            
            # Upload the JSON data to the blob
            blob_client.upload_blob(json.dumps(transformed_data, indent=2), overwrite=True)
            
            return JsonResponse({"message": "Question saved successfully", "id": filename}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    def get(self, request, question_id=None):
        if question_id:
            try:
                # Get a specific question
                blob_client = container_client.get_blob_client(f"{settings.MCQ_FOLDER}{question_id}")
                question_data = json.loads(blob_client.download_blob().readall().decode('utf-8'))
                return JsonResponse(question_data)
            except Exception as e:
                return JsonResponse({"error": str(e)}, status=404)
        else:
            # List all questions
            questions = []
            blob_list = container_client.list_blobs(name_starts_with=settings.MCQ_FOLDER)
            for blob in blob_list:
                if blob.name.endswith('.json'):
                    questions.append(blob.name.split('/')[-1])
            return JsonResponse({"questions": questions})
    # ... (keep get method unchanged)

    def transform_data(self, data):
        question_type = data.get('type', '').upper()
        transformed = {
            "Name": "",
            "ConceptID": "",
            "CreatedOn": time.strftime("%d-%m-%Y %H:%M:%S"),
            "QnTy": self.get_question_type(question_type),
            "MultiSelect": 1 if data.get('multiSelect') == 'Yes' else 0,
            "QnTe": data.get('template', ''),
            "Qn": data.get('question', ''),
            "QnPh": data.get('mediaFile', '') or "",
            "Type": "SNP_DIVQNS",
            "Option": [],
            "Expl": [
                {"SL": expl, "Type": "SNP_DIVSOL"}
                for expl in data.get('explanations', [])
            ],
            "Hint": [
                {"SL": hint, "Type": "SNP_DIVHINT"}
                for hint in data.get('hints', [])
            ]
        }

        if question_type == 'MCQ':
            correct_answers = data.get('correctAnswers', [])
            transformed["QnTy"] = "CM" if len(correct_answers) > 1 else "CO"
            transformed["Option"] = [
                {"Opt": opt, "Type": "SNP_OPTA" if opt in correct_answers else "SNP_OPT"}
                for opt in data.get('options', [])
            ]
        elif question_type == 'FITB':
            has_options = data.get('hasOptions') == 'Yes'
            is_multi_select = data.get('multiSelect') == 'Yes'
            transformed["QnTy"] = "CF"
            
            if has_options:
                if is_multi_select:
                    # Handle multi-blank questions
                    transformed["Option"] = [
                        {"Opt": opt.split(', ')[0], "Type": f"SNP_OPTA, {opt.split(', ')[1]}" if any(ans['option'] == opt.split(', ')[0] and ans['blank'] == opt.split(', ')[1] for ans in data.get('correctAnswers', [])) else "SNP_OPT"}
                        for opt in data.get('options', [])
                    ]
                else:
                    # Handle single-blank questions with options
                    transformed["Option"] = [
                        {"Opt": opt, "Type": "SNP_OPTA" if opt in data.get('correctAnswers', []) else "SNP_OPT"}
                        for opt in data.get('options', [])
                    ]
            else:
                # Handle questions without options
                transformed["Option"] = [
                    {"Opt": answer, "Type": "SNP_OPTA"}
                    for answer in data.get('correctAnswers', [])
                ]
        elif question_type == 'TF':
            transformed["QnTy"] = "CO"
            transformed["Option"] = [
                {"Opt": "True", "Type": "SNP_OPTA" if data.get('correctAnswers')[0] == "True" else "SNP_OPT"},
                {"Opt": "False", "Type": "SNP_OPTA" if data.get('correctAnswers')[0] == "False" else "SNP_OPT"}
            ]
        elif question_type == 'MATCH':
            transformed["QnTy"] = "CM"
            transformed["Option"] = [
                {"Opt": pair['left'], "Type": pair['right']}
                for pair in data.get('matchingPairs', [])
            ]

        return transformed

    def get_question_type(self, question_type):
        if question_type == 'MCQ':
            return 'C'  # This will be updated to CO or CM in transform_data
        elif question_type == 'FITB':
            return 'CF'
        elif question_type == 'TF':
            return 'CO'
        elif question_type == 'MATCH':
            return 'CM'
        else:
            return 'C'
