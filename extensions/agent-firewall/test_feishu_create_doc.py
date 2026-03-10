import os
import lark_oapi as lark
from lark_oapi.api.docx.v1 import CreateDocumentRequest, CreateDocumentRequestBody
from dotenv import load_dotenv

# Load .env from extension directory
load_dotenv(".env")

app_id = os.getenv("AF_FEISHU_APP_ID")
app_secret = os.getenv("AF_FEISHU_APP_SECRET")

if not app_id or not app_secret:
    print("Error: Feishu credentials not found in .env")
    exit(1)

print(f"Testing Feishu API with App ID: {app_id}")

# Initialize Client
client = lark.Client.builder() \
    .app_id(app_id) \
    .app_secret(app_secret) \
    .log_level(lark.LogLevel.DEBUG) \
    .build()

def create_doc():
    # Construct request
    # Note: folder_token is usually optional, defaults to root
    request = CreateDocumentRequest.builder() \
        .request_body(CreateDocumentRequestBody.builder()
            .title("今天北京的天气 (Test via Agent Firewall)")
            .build()) \
        .build()

    # Call API
    response = client.docx.v1.document.create(request)

    # Handle response
    if not response.success():
        print(f"Failed to create document: {response.code}")
        print(f"Message: {response.msg}")
        print(f"Error: {response.error}")
        return

    doc = response.data.document
    print(f"Successfully created document!")
    print(f"Title: {doc.title}")
    print(f"Document ID: {doc.document_id}")
    # Construct URL (assuming standard Lark/Feishu domain)
    # The response might not contain the full URL, but we can construct it.
    # Usually it's https://<tenant>.feishu.cn/docx/<document_id>
    print(f"Document Token: {doc.document_id}")

if __name__ == "__main__":
    create_doc()
