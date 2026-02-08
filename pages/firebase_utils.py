import requests
import json
import os
from django.conf import settings
from django.core.cache import cache
import logging
import mimetypes
from datetime import timedelta


logger = logging.getLogger(__name__)




class FirebaseConfig:
    """Firebase configuration class"""
    def __init__(self):
        self.api_key = os.environ.get('FIREBASE_API_KEY') or getattr(settings, 'FIREBASE_API_KEY', None) or 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM'
        self.project_id = getattr(settings, 'FIREBASE_PROJECT_ID', 'kobey-e0eca')
        self.storage_bucket = f"{self.project_id}.appspot.com"
        self.base_url = f"https://firestore.googleapis.com/v1/projects/{self.project_id}/databases/(default)/documents"
        if not self.api_key:
            raise ValueError("Firebase API key not available")


config = FirebaseConfig()


class FirestoreClient:

    def __init__(self):
        self.config = config

    def query_collection(self, collection, filters=None, order_by=None, limit=None):
        """
        Query a Firestore collection using the REST API.
        Supports filters (list of dicts), order_by (dict), and limit (int).
        """
        # If filters is a list of dicts, use query_firestore_collection_with_multiple_filters
        if filters:
            # Only support simple AND filters for now
            from .firebase_utils import query_firestore_collection_with_multiple_filters
            results = query_firestore_collection_with_multiple_filters(collection, filters)
        else:
            # No filters, get all documents (limit if provided)
            from .firebase_utils import get_all_documents_from_collection
            results = get_all_documents_from_collection(collection, limit=limit or 100)
        # Optionally sort in Python if order_by is provided
        if order_by:
            for field, direction in order_by.items():
                reverse = (str(direction).lower() in ['desc', 'descending'])
                results = sorted(results, key=lambda x: x.get(field, ''), reverse=reverse)
        # Optionally limit results
        if limit:
            results = results[:limit]
        return results

    def _make_request(self, method, url, params=None, json_data=None):
        if params is None:
            params = {}
        params['key'] = self.config.api_key
        if 'token' in params:
            logger.warning("Removing unexpected 'token' from Firestore REST API params")
            params.pop('token')
        try:
            response = requests.request(method, url, params=params, json=json_data, timeout=30)
            logger.info(f"{method} {url} - Status: {response.status_code}")
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    def get_document(self, collection, document_id, use_cache=True, cache_timeout=300):
        import hashlib
        if not isinstance(document_id, str) or not document_id.isalnum():
            safe_document_id = hashlib.md5(str(document_id).encode()).hexdigest()
        else:
            safe_document_id = document_id
        cache_key = f"firestore_{collection}_{safe_document_id}"
        if use_cache:
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
        url = f"{self.config.base_url}/{collection}/{document_id}"
        logger.info(f"[Firestore] GET URL: {url}")
        response = self._make_request('GET', url)
        logger.info(f"[Firestore] GET params: key={self.config.api_key}")
        logger.info(f"[Firestore] Response status: {response.status_code}")
        logger.info(f"[Firestore] Response text: {response.text}")
        if response.status_code == 200:
            data = response.json()
            result = self._convert_firestore_document(data)
            if use_cache:
                cache.set(cache_key, result, cache_timeout)
            return result
        elif response.status_code == 404:
            logger.warning(f"[Firestore] Document {document_id} not found in {collection}. URL: {url}")
            logger.warning(f"[Firestore] Response text: {response.text}")
            return None
        else:
            logger.error(f"[Firestore] Error getting document: {response.status_code} - {response.text}")
            return None

    def set_document(self, collection, document_id, data):
        url = f"{self.config.base_url}/{collection}/{document_id}"
        firestore_data = {"fields": self._convert_to_firestore_format(data)}
        response = self._make_request('PATCH', url, json_data=firestore_data)
        if response.status_code == 200:
            logger.info(f"✅ Set document {document_id} in {collection} via REST API")
            cache.delete(f"firestore_{collection}_{document_id}")
            return True
        else:
            logger.error(f"❌ Set failed: {response.status_code} - {response.text}")
            return False

    def update_document(self, collection, document_id, updates):
        url = f"{self.config.base_url}/{collection}/{document_id}"
        params = {'updateMask.fieldPaths': list(updates.keys())}
        firestore_data = {"fields": self._convert_to_firestore_format(updates)}
        response = self._make_request('PATCH', url, params=params, json_data=firestore_data)
        if response.status_code == 200:
            logger.info(f"✅ Updated document {document_id} in {collection} via REST API")
            cache.delete(f"firestore_{collection}_{document_id}")
            return True
        else:
            logger.error(f"❌ Update failed: {response.status_code} - {response.text}")
            return False

    def delete_document(self, collection, document_id):
        url = f"{self.config.base_url}/{collection}/{document_id}"
        response = self._make_request('DELETE', url)
        if response.status_code == 200:
            logger.info(f"✅ Deleted document {document_id} from {collection}")
            cache.delete(f"firestore_{collection}_{document_id}")
            return True
        else:
            logger.error(f"❌ Delete failed: {response.status_code} - {response.text}")
            return False
    def _convert_to_firestore_format(self, data):
        """Convert a Python dict to Firestore REST API format (fields dict)."""
        def convert_value(value):
            if value is True:
                return {"booleanValue": True}
            elif value is False:
                return {"booleanValue": False}
            elif isinstance(value, str):
                return {"stringValue": value}
            elif isinstance(value, int):
                return {"integerValue": str(value)}
            elif isinstance(value, float):
                return {"doubleValue": value}
            elif isinstance(value, list):
                return {"arrayValue": {"values": [convert_value(v) for v in value]}}
            elif value is None:
                return {"nullValue": None}
            elif isinstance(value, dict):
                return {"mapValue": {"fields": {k: convert_value(v) for k, v in value.items()}}}
            else:
                return {"stringValue": str(value)}
        return {k: convert_value(v) for k, v in data.items()}

    def _convert_firestore_document(self, firestore_doc):
        """Convert Firestore REST API document to a Python dict."""
        def convert_value(value):
            if 'stringValue' in value:
                return value['stringValue']
            elif 'integerValue' in value:
                return int(value['integerValue'])
            elif 'doubleValue' in value:
                return float(value['doubleValue'])
            elif 'booleanValue' in value:
                return value['booleanValue']
            elif 'nullValue' in value:
                return None
            elif 'timestampValue' in value:
                return value['timestampValue']
            elif 'arrayValue' in value:
                return [convert_value(item) for item in value['arrayValue'].get('values', [])]
            elif 'mapValue' in value:
                return {k: convert_value(v) for k, v in value['mapValue'].get('fields', {}).items()}
            else:
                return value
        if 'fields' not in firestore_doc:
            return None
        return {k: convert_value(v) for k, v in firestore_doc['fields'].items()}
def get_firestore_document(collection, document_id):
    """Get Firestore document via REST API using API key"""
    url = f"https://firestore.googleapis.com/v1/projects/kobey-e0eca/databases/(default)/documents/{collection}/{document_id}"
    
    params = {
        'key': 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM'
    }
    # Remove any accidental 'token' field from params
    if 'token' in params:
        params.pop('token')
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            # Convert Firestore format to simple dict
            return convert_firestore_document(data)
        elif response.status_code == 404:
            print(f"Document {document_id} not found in {collection}")
            return None
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error getting Firestore document: {e}")
        return None

def convert_firestore_document(firestore_doc):
    """Convert Firestore document format to simple dict"""
    if 'fields' not in firestore_doc:
        return None
    
    result = {}
    fields = firestore_doc['fields']
    
    for key, value in fields.items():
        # Handle different Firestore field types
        if 'stringValue' in value:
            result[key] = value['stringValue']
        elif 'integerValue' in value:
            result[key] = int(value['integerValue'])
        elif 'doubleValue' in value:
            result[key] = float(value['doubleValue'])
        elif 'booleanValue' in value:
            result[key] = value['booleanValue']
        elif 'nullValue' in value:
            result[key] = None
        else:
            # Handle other types as needed
            result[key] = value
    
    return result

def get_firestore_subcollection(collection, document_id, subcollection):
    """Get subcollection documents via REST API"""
    url = f"https://firestore.googleapis.com/v1/projects/kobey-e0eca/databases/(default)/documents/{collection}/{document_id}/{subcollection}"
    
    params = {
        'key': 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM'
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            documents = data.get('documents', [])
            return [convert_firestore_document(doc) for doc in documents]
        else:
            print(f"Error getting subcollection: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error getting subcollection: {e}")
        return []

def query_firestore_collection(collection, field, operator, value):
    """Query Firestore collection via REST API"""
    url = f"https://firestore.googleapis.com/v1/projects/kobey-e0eca/databases/(default)/documents:runQuery"
    
    params = {
        'key': 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM'
    }
    # Remove any accidental 'token' field from params
    if 'token' in params:
        params.pop('token')
    
    query = {
        "structuredQuery": {
            "from": [{"collectionId": collection}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": field},
                    "op": operator,
                    "value": {"stringValue": value}
                }
            }
        }
    }
    
    try:
        response = requests.post(url, params=params, json=query)
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data:
                if 'document' in item:
                    results.append(convert_firestore_document(item['document']))
            return results
        else:
            print(f"Query error: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error querying collection: {e}")
        return []
    
def update_firestore_document(collection, document_id, updates):
    """Update Firestore document via REST API"""
    url = f"https://firestore.googleapis.com/v1/projects/kobey-e0eca/databases/(default)/documents/{collection}/{document_id}"
    
    # Remove any accidental 'token' field from updates
    updates = {k: v for k, v in updates.items() if k != 'token'}
    params = {
        'key': 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM',
        'updateMask.fieldPaths': list(updates.keys())
    }

    # Convert updates to Firestore format
    firestore_fields = {}
    for key, value in updates.items():
        # if key == 'token':
        #     continue
        if isinstance(value, str):
            firestore_fields[key] = {"stringValue": value}
        elif isinstance(value, int):
            firestore_fields[key] = {"integerValue": str(value)}
        elif isinstance(value, float):
            firestore_fields[key] = {"doubleValue": value}
        elif isinstance(value, bool):
            firestore_fields[key] = {"booleanValue": value}
        elif value is None:
            firestore_fields[key] = {"nullValue": None}

    data = {
        "fields": firestore_fields
    }

    try:
        response = requests.patch(url, params=params, json=data)
        if response.status_code == 200:
            print(f"✅ Updated document {document_id} in {collection}")
            return True
        else:
            print(f"❌ Update failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error updating document: {e}")
        return False

def set_firestore_document(collection, document_id, data):
    """Set/create Firestore document via REST API"""
    url = f"https://firestore.googleapis.com/v1/projects/kobey-e0eca/databases/(default)/documents/{collection}/{document_id}"
    
    params = {
        'key': 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM'
    }
    # Remove any accidental 'token' field from params
    if 'token' in params:
        params.pop('token')
    # Remove any accidental 'token' field from data
    data = {k: v for k, v in data.items() if k != 'token'}
    # Convert data to Firestore format
    firestore_fields = {}
    for key, value in data.items():
        if isinstance(value, str):
            firestore_fields[key] = {"stringValue": value}
        elif isinstance(value, int):
            firestore_fields[key] = {"integerValue": str(value)}
        elif isinstance(value, float):
            firestore_fields[key] = {"doubleValue": value}
        elif isinstance(value, bool):
            firestore_fields[key] = {"booleanValue": value}
        elif value is None:
            firestore_fields[key] = {"nullValue": None}
    document_data = {
        "fields": firestore_fields
    }
    
    try:
        response = requests.patch(url, params=params, json=document_data)
        if response.status_code == 200:
            print(f"✅ Set document {document_id} in {collection}")
            return True
        else:
            print(f"❌ Set failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error setting document: {e}")
        return False

def delete_firestore_document(collection, document_id):
    """Delete Firestore document via REST API"""
    url = f"https://firestore.googleapis.com/v1/projects/kobey-e0eca/databases/(default)/documents/{collection}/{document_id}"
    
    params = {
        'key': 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM'
    }
    # Remove any accidental 'token' field from params
    if 'token' in params:
        params.pop('token')
    
    try:
        response = requests.delete(url, params=params)
        if response.status_code == 200:
            print(f"✅ Deleted document {document_id} from {collection}")
            return True
        else:
            print(f"❌ Delete failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error deleting document: {e}")
        return False
# def get_firestore_document(collection_name, document_id):
#     """Get a single document from Firestore via REST API"""
#     url = f"https://firestore.googleapis.com/v1/projects/kobey-e0eca/databases/(default)/documents/{collection_name}/{document_id}"
    
#     params = {
#         'key': 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM'
#     }
    
#     try:
#         response = requests.get(url, params=params, timeout=10)
        
#         if response.status_code == 200:
#             doc_data = response.json()
            
#             # Check if document exists and has fields
#             if 'fields' in doc_data:
#                 converted_doc = convert_firestore_document(doc_data)
#                 print(f"Found document {document_id} in {collection_name}")
#                 return converted_doc
#             else:
#                 print(f"Document {document_id} exists but has no fields in {collection_name}")
#                 return None
                
#         elif response.status_code == 404:
#             print(f"Document {document_id} not found in {collection_name}")
#             return None
#         else:
#             print(f"Error retrieving document {document_id}: {response.status_code}")
#             print(f"Response: {response.text}")
#             return None
            
#     except Exception as e:
#         print(f"Error getting document {document_id} from {collection_name}: {e}")
#         return None    

def get_firestore_document(collection, document_id):
    """Get Firestore document via REST API using API key"""
    url = f"https://firestore.googleapis.com/v1/projects/kobey-e0eca/databases/(default)/documents/{collection}/{document_id}"
    
    params = {
        'key': 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM'
    }
    # Remove any accidental 'token' field from params
    if 'token' in params:
        params.pop('token')
    
    try:
        logger.info(f"🔥 Fetching from Firestore: {collection}/{document_id}")
        response = requests.get(url, params=params)
        logger.info(f"🔥 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"🔥 Response has 'fields': {'fields' in data}")
            # Convert Firestore format to simple dict
            result = convert_firestore_document(data)
            logger.info(f"🔥 Converted document keys: {list(result.keys()) if result else 'None'}")
            return result
        elif response.status_code == 404:
            logger.error(f"❌ Document {document_id} not found in {collection}")
            print(f"Document {document_id} not found in {collection}")
            return None
        else:
            logger.error(f"❌ Error: {response.status_code} - {response.text}")
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"❌ Error getting Firestore document: {e}")
        print(f"Error getting Firestore document: {e}")
        return None

def convert_firestore_document(firestore_doc):
    """Convert Firestore document format to simple dict"""
    if 'fields' not in firestore_doc:
        return None
    
    result = {}
    fields = firestore_doc['fields']
    
    for key, value in fields.items():
        result[key] = convert_firestore_value(value)
    
    return result

def convert_firestore_value(value):
    """Convert a Firestore value to Python value"""
    if 'stringValue' in value:
        return value['stringValue']
    elif 'integerValue' in value:
        return int(value['integerValue'])
    elif 'doubleValue' in value:
        return float(value['doubleValue'])
    elif 'booleanValue' in value:
        return value['booleanValue']
    elif 'nullValue' in value:
        return None
    elif 'timestampValue' in value:
        return value['timestampValue']
    elif 'arrayValue' in value:
        return [convert_firestore_value(item) for item in value['arrayValue'].get('values', [])]
    elif 'mapValue' in value:
        result = {}
        for k, v in value['mapValue'].get('fields', {}).items():
            result[k] = convert_firestore_value(v)
        return result
    else:
        # Return the raw value if we don't know how to convert it
        return value

def get_firestore_subcollection(collection, document_id, subcollection):
    """Get subcollection documents via REST API"""
    url = f"https://firestore.googleapis.com/v1/projects/kobey-e0eca/databases/(default)/documents/{collection}/{document_id}/{subcollection}"
    
    params = {
        'key': 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM'
    }
    # Remove any accidental 'token' field from params
    if 'token' in params:
        params.pop('token')
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            documents = data.get('documents', [])
            return [convert_firestore_document(doc) for doc in documents]
        else:
            print(f"Error getting subcollection: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error getting subcollection: {e}")
        return []

def query_firestore_collection(collection, field, operator, value):
    """Query Firestore collection via REST API"""
    url = f"https://firestore.googleapis.com/v1/projects/kobey-e0eca/databases/(default)/documents:runQuery"
    
    params = {
        'key': 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM'
    }
    
    query = {
        "structuredQuery": {
            "from": [{"collectionId": collection}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": field},
                    "op": operator,
                    "value": convert_value_to_firestore_format(value)
                }
            }
        }
    }
    
    try:
        response = requests.post(url, params=params, json=query)
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data:
                if 'document' in item:
                    results.append(convert_firestore_document(item['document']))
            return results
        else:
            print(f"Query error: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error querying collection: {e}")
        return []
def convert_value_to_firestore_format(value):
    """Convert Python values to Firestore REST API format"""
    if value is True:
        return {"booleanValue": True}
    elif value is False:
        return {"booleanValue": False}
    elif isinstance(value, str):
        return {"stringValue": value}
    elif isinstance(value, int):
        return {"integerValue": str(value)}
    elif isinstance(value, float):
        return {"doubleValue": value}
    elif isinstance(value, list):
        return {
            "arrayValue": {
                "values": [convert_value_to_firestore_format(item) for item in value]
            }
        }
    elif value is None:
        return {"nullValue": None}
    else:
        # Fallback - treat as string
        return {"stringValue": str(value)}
# def convert_value_to_firestore_format(value):
#     """Convert Python value to Firestore format"""
#     if isinstance(value, str):
#         return {"stringValue": value}
#     elif isinstance(value, int):
#         return {"integerValue": str(value)}
#     elif isinstance(value, float):
#         return {"doubleValue": value}
#     elif isinstance(value, bool):
#         return {"booleanValue": value}
#     elif isinstance(value, list):
#         return {"arrayValue": {"values": [convert_value_to_firestore_format(v) for v in value]}}
#     elif value is None:
#         return {"nullValue": None}
#     else:
#         return {"stringValue": str(value)}

def query_firestore_collection_with_multiple_filters(collection, filters):
    """
    Query Firestore collection with multiple filters
    
    Args:
        collection (str): Collection name
        filters (list): List of filter dictionaries with 'field', 'operator', 'value'
    
    Returns:
        list: List of documents matching all filters
    """
    url = f"https://firestore.googleapis.com/v1/projects/kobey-e0eca/databases/(default)/documents:runQuery"
    
    params = {
        'key': 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM'
    }
    # Remove any accidental 'token' field from params
    if 'token' in params:
        params.pop('token')
    
    # Build the structured query with multiple filters
    where_conditions = []
    for filter_item in filters:
        field_filter = {
            "fieldFilter": {
                "field": {"fieldPath": filter_item['field']},
                "op": filter_item['operator'],
                "value": convert_value_to_firestore_format(filter_item['value'])
            }
        }
        where_conditions.append(field_filter)
    
    # Combine filters with AND operator
    if len(where_conditions) == 1:
        where_clause = where_conditions[0]
    else:
        where_clause = {
            "compositeFilter": {
                "op": "AND",
                "filters": where_conditions
            }
        }
    
    query = {
        "structuredQuery": {
            "from": [{"collectionId": collection}],
            "where": where_clause
        }
    }
    
    try:
        response = requests.post(url, params=params, json=query)
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data:
                if 'document' in item:
                    results.append(convert_firestore_document(item['document']))
            return results
        else:
            print(f"Query error: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Error querying collection with multiple filters: {e}")
        return []

# def update_firestore_document(collection, document_id, updates):
#     """Update Firestore document via REST API"""
#     url = f"https://firestore.googleapis.com/v1/projects/kobey-e0eca/databases/(default)/documents/{collection}/{document_id}"
    
#     params = {
#         'key': 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM',
#         'updateMask.fieldPaths': list(updates.keys())
#     }
    
#     # Convert updates to Firestore format
#     firestore_fields = {}
#     for key, value in updates.items():
#         firestore_fields[key] = convert_value_to_firestore_format(value)
    
#     data = {
#         "fields": firestore_fields
#     }
    
#     try:
#         response = requests.patch(url, params=params, json=data)
#         if response.status_code == 200:
#             print(f"✅ Updated document {document_id} in {collection}")
#             return True
#         else:
#             print(f"❌ Update failed: {response.status_code} - {response.text}")
#             return False
#     except Exception as e:
#         print(f"❌ Error updating document: {e}")
#         return False

# NEW FUNCTIONS FOR DASHHOME:
# Create global client instance
firestore_client = FirestoreClient()

def get_banners_by_state(state):
    """Get banners that include the specified state"""
    try:
        # First get all active banners
        active_banners = query_firestore_collection('dealweeks', 'display', 'EQUAL', True)
        
        # Filter by state_list containing the state
        state_banners = []
        for banner in active_banners:
            state_list = banner.get('state_list', [])
            if isinstance(state_list, list) and state in state_list:
                state_banners.append(banner)
                if len(state_banners) >= 10:  # Limit to 10
                    break
        
        return state_banners
    except Exception as e:
        print(f"Error getting banners by state: {e}")
        return []

def get_verified_restaurants_by_state(state, limit=10):
    """Get verified restaurants in a specific state"""
    try:
        # Use multiple filters: state and verified status
        filters = [
            {'field': 'restoState', 'operator': 'EQUAL', 'value': state},
            {'field': 'is_verified', 'operator': 'EQUAL', 'value': True}
        ]
        
        restaurants = query_firestore_collection_with_multiple_filters('restaurants', filters)
        return restaurants[:limit]
    except Exception as e:
        print(f"Error getting verified restaurants: {e}")
        return []

def get_verified_stores_by_state(state, limit=10):
    """Get verified stores in a specific state"""
    try:
        # Use multiple filters: state and verified status
        filters = [
            {'field': 'state', 'operator': 'EQUAL', 'value': state},
            {'field': 'is_verified', 'operator': 'EQUAL', 'value': True}
        ]
        
        stores = query_firestore_collection_with_multiple_filters('stores', filters)
        return stores[:limit]
    except Exception as e:
        print(f"Error getting verified stores: {e}")
        return []

def query_firestore_collection_with_array_contains(collection, field, value):
    """Query Firestore collection where array field contains a specific value"""
    url = f"https://firestore.googleapis.com/v1/projects/kobey-e0eca/databases/(default)/documents:runQuery"
    
    params = {
        'key': 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM'
    }
    # Remove any accidental 'token' field from params
    if 'token' in params:
        params.pop('token')
    
    query = {
        "structuredQuery": {
            "from": [{"collectionId": collection}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": field},
                    "op": "ARRAY_CONTAINS",
                    "value": convert_value_to_firestore_format(value)
                }
            }
        }
    }
    
    try:
        response = requests.post(url, params=params, json=query)
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data:
                if 'document' in item:
                    results.append(convert_firestore_document(item['document']))
            return results
        else:
            print(f"Array contains query error: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Error querying array contains: {e}")
        return []

def test_firebase_connection():
    """Test if Firebase is working"""
    try:
        # Try a simple query
        test_data = query_firestore_collection('test', 'exists', 'EQUAL', True)
        print("✅ Firebase connection test successful")
        return True
    except Exception as e:
        print(f"❌ Firebase connection test failed: {e}")
        return False

def debug_firebase_status():
    """Debug function to check Firebase status"""
    print("=== Firebase Debug Info ===")
    print("Using Firestore REST API")
    print("API Key: AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM")
    print("Project ID: kobey-e0eca")
    
    try:
        # Test connection
        if test_firebase_connection():
            print("✅ Firebase REST API accessible")
        else:
            print("❌ Firebase REST API connection failed")
    except Exception as e:
        print(f"❌ Firebase debug error: {e}")

# Utility functions
def get_all_documents_from_collection(collection, limit=50):
    """Get all documents from a collection with limit"""
    url = f"https://firestore.googleapis.com/v1/projects/kobey-e0eca/databases/(default)/documents/{collection}"
    
    params = {
        'key': 'AIzaSyDqSdny0vyx7p8qoJ9RRzC_cQk2iaAWqCM',
        'pageSize': limit
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            documents = data.get('documents', [])
            return [convert_firestore_document(doc) for doc in documents]
        else:
            print(f"Get collection error: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Error getting collection: {e}")
        return []


class FirebaseStorageClient:
    """Firebase Storage client for file uploads (REST API only stub)"""
    def __init__(self):
        self.config = config

    def upload_file(self, file_obj, destination_path):
        logger.error("Firebase Storage upload is not supported without Admin SDK. Use Google Cloud Storage REST API or another method.")
        return None

    def delete_file(self, file_path):
        logger.error("Firebase Storage delete is not supported without Admin SDK. Use Google Cloud Storage REST API or another method.")
        return False
