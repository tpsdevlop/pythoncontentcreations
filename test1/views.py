from django.http import HttpResponse, JsonResponse, HttpResponseNotFound
import json
from rest_framework.decorators import api_view
import os
from django.views.decorators.csrf import csrf_exempt
import pymongo
from azure.storage.blob import BlobServiceClient

AZURE_ACCOUNT_NAME = 'storeholder'
AZURE_ACCOUNT_KEY = 'QxlUJdp8eSoPeQPas4NigSkXg6KMep7z+fPQ5CpPm0kRfjg7Q0lFmVEIyhU4ohFLFdSqntDAG6MY84elTfecnw=='
AZURE_CONTAINER = 'tpdata'
blob_service_client = BlobServiceClient(account_url=f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/",credential=AZURE_ACCOUNT_KEY)
container_client = blob_service_client.get_container_client(AZURE_CONTAINER)

def get_blob_file(request):
    try:
        BLOB_NAME = 'Syllabus/PYTHON/Python1.json'
        container_client = blob_service_client.get_container_client(AZURE_CONTAINER)
        blob_client = container_client.get_blob_client(BLOB_NAME)
        download_stream = blob_client.download_blob()
        json_data = download_stream.readall()
        return HttpResponse(json_data, content_type='application/json')
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@csrf_exempt
def check_email(request, email):
    client = pymongo.MongoClient("mongodb+srv://ranjithagowda5182:uR5X3yE7jC6cmmnv@cluster0.vksfphs.mongodb.net/")
    db = client["PythonDB"]
    collection = db["LoginDB"]
    if request.method == "GET":
        user = collection.find_one({"email": email})
        if user:
            email_type = user.get("Type")
            return JsonResponse({'exists': True,'Type':email_type})
        else:
            return JsonResponse({'exists': False})
    return JsonResponse({'error': 'Invalid request method'}, status=400)

def get_file(request, concept, filename):
    try:
        blob_path = f'Question/{concept}/{filename}'  # Assuming concept is the "folder" and filename is the actual file name
        blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER, blob=blob_path)
        if blob_client.exists():
            file_content = blob_client.download_blob().readall().decode('utf-8')
            return JsonResponse({'fileContent': file_content})
        else:
            return HttpResponseNotFound('<h1>File not found</h1>')
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@csrf_exempt
def get_files_in_folder(request, concept):
    try:
        concept_folder_path = f'Question/{concept}/'
        blobs = container_client.list_blobs(name_starts_with=concept_folder_path)
        files = []
        file_contents = {}
        for blob in blobs:
            file_name = blob.name[len(concept_folder_path):] 
            files.append(file_name)
            blob_client = container_client.get_blob_client(blob)
            file_contents[file_name] = blob_client.download_blob().readall().decode('utf-8')
        return JsonResponse({'files': files, 'contents': file_contents})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@api_view(['POST'])
@csrf_exempt
def save_json(request):
    if request.method == "POST":
        try:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON data format'}, status=400)
            concept = data.get('ConceptID')
            qtype = data.get('QuestionType')
            level = data.get('Level')
            if not all([concept, qtype, level]):
                return JsonResponse({'error': 'Required fields are missing'}, status=400)
            if qtype == "exercise":
                filename_prefix = 'Q'
            elif qtype == "test":
                filename_prefix = 'T'
            else:
                return JsonResponse({'error': 'Invalid QuestionType'}, status=400)
            if level == "easy":
                time = 'A'
                level_code = 'E'
            elif level == "medium":
                time = 'B'
                level_code = 'M'
            elif level == "hard":
                time = 'C'
                level_code = 'H'
            else:
                return JsonResponse({'error': 'Invalid Level'}, status=400)
            blob_service_client = BlobServiceClient(account_url=f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/",credential=AZURE_ACCOUNT_KEY)
            container_client = blob_service_client.get_container_client(AZURE_CONTAINER)
            if not container_client.exists():
                container_client.create_container()
            just_filename=f'{filename_prefix}{concept}{time}XX{level_code}M'
            final_filename = f'Question/{concept}/'
            blobs = list(container_client.list_blobs(name_starts_with=f'Question/{concept}/{filename_prefix}'))
            num_of_files = sum(1 for blob in blobs if blob.name.startswith(f'Question/{concept}/{filename_prefix}'))
            just_filename += f'{str(num_of_files + 1).zfill(2)}.json'
            final_filename+=just_filename
            if 'currentFile' in data:
                current_file_path = f'Question/{concept}/{data["currentFile"]}'
                blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER, blob=current_file_path)
                if blob_client.exists():
                    existing_data = blob_client.download_blob().readall().decode('utf-8')
                    existing_json = json.loads(existing_data)
                    data['CreatedON'] = existing_json.get('CreatedON', '')
                    blob_client.delete_blob()
                    final_filename=f'Question/{concept}/{data["currentFile"]}'            
            print(just_filename)
            document = {
                "QuestionId": just_filename[:-5],
                "CreatedBy": data.get("CreatedBy", ""),
                "CreatedTime": data.get("CreatedON", ""),
                "ReviewedBy": request.GET.get("ReviewedBy", ""),
                "ReviewedTime": request.GET.get("ReviewedTime", ""),
                "Approved": request.GET.get("Approved", "N"),
                "Last_Updated": data.get("Last_Updated", ""),
                "Comments": request.GET.get("Comments", "")
            }
            with pymongo.MongoClient("mongodb+srv://ranjithagowda5182:uR5X3yE7jC6cmmnv@cluster0.vksfphs.mongodb.net/") as client:
                db = client["PythonDB"]
                collection = db["questioninfo"]
                if 'currentFile' in data and data['currentFile']!='':
                    currentfile = data['currentFile']
                    print('check',currentfile)
                    collection.update_one({"QuestionId": currentfile[:-5]}, {"$set": {
                        "QuestionId": currentfile[:-5],
                        "Last_Updated": data.get("LastUpdated", "")
                    }})
                    del data['currentFile']
                else:
                    collection.insert_one(document)
            json_data = json.dumps(data, ensure_ascii=False, indent=4)
            blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER, blob=final_filename)
            blob_client.upload_blob(json_data, overwrite=True)
            return JsonResponse({"message": "JSON data received and saved successfully."})
        except ConnectionError:
            return JsonResponse({'error': 'Database connection failed'}, status=500)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)

@api_view(['POST'])
@csrf_exempt
def submitReview(request):
    if request.method == "POST":
        try:
            with pymongo.MongoClient("mongodb+srv://ranjithagowda5182:uR5X3yE7jC6cmmnv@cluster0.vksfphs.mongodb.net/") as client:
                db = client["PythonDB"]
                collection = db["questioninfo"]
                try:
                    data = json.loads(request.body)
                    file = data.get('file')
                    collection.update_one({"QuestionId": file[:-5]}, {"$set": {
                        "ReviewedBy": data.get("reviewedBy"),
                        "ReviewedTime": data.get("reviewedTime"),
                        "Comments": data.get("comments"),
                        "Approved": data.get("approved"),
                    }})
                    return JsonResponse({'message': 'Review updated successfully'})
                except json.JSONDecodeError:
                    return JsonResponse({'error': 'Invalid JSON data format'}, status=400)
        except ConnectionError:
            return JsonResponse({'error': 'Database connection failed'}, status=500)
        except Exception as e:
            print(f"Unexpected error: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)
    
def get_filtered_files(folder_name, approved, file_type):
    try:
        with pymongo.MongoClient("mongodb+srv://ranjithagowda5182:uR5X3yE7jC6cmmnv@cluster0.vksfphs.mongodb.net/") as client:
            db = client["PythonDB"]
            collection = db["questioninfo"]
            query = {"Approved": approved}
            results = collection.find(query)
            db_filenames = [result["QuestionId"] + ".json" for result in results]
        folder_path = f'Question/{folder_name}/'
        blobs = container_client.list_blobs(name_starts_with=folder_path)
        files = [os.path.basename(blob.name) for blob in blobs]
        filtered_files = [file for file in files if file in db_filenames and file.startswith(file_type)]
        return filtered_files
    except Exception as e:
        return {'error': str(e)}

def n_q_folder_contents(request, folder_name):
    filtered_files = get_filtered_files(folder_name, "N", "Q")
    return JsonResponse({'files': filtered_files})

def n_t_folder_contents(request, folder_name):
    filtered_files = get_filtered_files(folder_name, "N", "T")
    return JsonResponse({'files': filtered_files})

def a_q_folder_contents(request, folder_name):
    filtered_files = get_filtered_files(folder_name, "Y", "Q")
    return JsonResponse({'files': filtered_files})

def a_t_folder_contents(request, folder_name):
    filtered_files = get_filtered_files(folder_name, "Y", "T")
    return JsonResponse({'files': filtered_files})

def file_content(request, folder_name, filename):
    try:
        blob_path = f'Question/{folder_name}/{filename}'
        blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER, blob=blob_path)
        if blob_client.exists():
            file_content = blob_client.download_blob().readall().decode('utf-8')
            return JsonResponse({'content': file_content})
        else:
            return HttpResponseNotFound('File not found')
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)