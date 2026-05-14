# TailorTalk-Drive-Agent

TailorTalk-Drive-Agent is a production-ready starter project for chatting with a Google Drive folder through natural language. It uses FastAPI, Streamlit, LangChain, Gemini, Google Drive API, a Google service account, and LangChain tool calling.

The agent can search for exact file names, partial file names, file contents, MIME types, created dates, modified dates, and natural language requests such as:

- Find financial report from last week
- Show PDF files modified yesterday
- Find image files
- Find reports containing sales
- Find spreadsheet from January

## Project Structure

```text
TailorTalk-Drive-Agent/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── agent.py
│   ├── drive_tool.py
│   ├── prompt.py
│   ├── requirements.txt
│   ├── .env.example
├── frontend/
│   ├── streamlit_app.py
│   ├── requirements.txt
├── .gitignore
├── README.md
```

## STEP 1: Install Python

1. Go to <https://www.python.org/downloads/>.
2. Download the latest stable Python 3 version.
3. During installation on Windows, check **Add Python to PATH**.
4. Open a new terminal and verify:

```powershell
py --version
```

If `py` does not work, try:

```powershell
python --version
```

## STEP 2: Install VS Code

1. Go to <https://code.visualstudio.com/>.
2. Download and install Visual Studio Code.
3. Open VS Code.
4. Install the official Python extension from Microsoft.

## STEP 3: Create/Open Folder

Create or open this folder:

```text
TailorTalk-Drive-Agent
```

In VS Code, use:

```text
File -> Open Folder
```

Then select the `TailorTalk-Drive-Agent` folder.

## STEP 4: Open Terminal

In VS Code:

```text
Terminal -> New Terminal
```

Make sure the terminal is inside your project folder.

## STEP 5: Google Cloud Project Creation

1. Go to <https://console.cloud.google.com/>.
2. Sign in with your Google account.
3. Click the project dropdown at the top.
4. Click **New Project**.
5. Name it something like `TailorTalk Drive Agent`.
6. Click **Create**.

## STEP 6: Enable Google Drive API

1. Open your Google Cloud project.
2. Go to **APIs & Services -> Library**.
3. Search for **Google Drive API**.
4. Open it.
5. Click **Enable**.

## STEP 7: Create Service Account

1. Go to **IAM & Admin -> Service Accounts**.
2. Click **Create Service Account**.
3. Name it `tailortalk-drive-agent`.
4. Click **Create and Continue**.
5. You do not need to grant project-wide roles for basic Drive file search.
6. Click **Done**.

## STEP 8: Download service-account.json

1. Open the service account you created.
2. Go to the **Keys** tab.
3. Click **Add Key -> Create new key**.
4. Choose **JSON**.
5. Download the file.
6. Rename it to:

```text
service-account.json
```

7. Move it into the `backend/` folder:

```text
TailorTalk-Drive-Agent/backend/service-account.json
```

Never commit this JSON file to GitHub. It is ignored by `.gitignore`.

## STEP 9: Share Google Drive Folder With Service Account Email

1. Open `service-account.json`.
2. Find the `client_email` value.
3. It looks like:

```text
tailortalk-drive-agent@your-project.iam.gserviceaccount.com
```

4. Go to Google Drive.
5. Right-click the folder you want the agent to search.
6. Click **Share**.
7. Paste the service account email.
8. Give it Viewer access.
9. Click **Send** or **Share**.

By default, the app searches all files visible to the service account. To restrict searches to one direct folder, set `GOOGLE_DRIVE_FOLDER_ID` in `.env`.

## STEP 10: Create .env

Copy this file:

```text
backend/.env.example
```

Create:

```text
backend/.env
```

Fill it in:

```env
GEMINI_API_KEY=your_real_gemini_api_key
GOOGLE_SERVICE_ACCOUNT_FILE=service-account.json
GOOGLE_DRIVE_FOLDER_ID=
GEMINI_MODEL=gemini-2.5-flash
```

Get a Gemini API key from Google AI Studio:

<https://aistudio.google.com/app/apikey>

## STEP 11: Run Backend

Open a terminal in the project root, then run:

```powershell
cd backend
py -m pip install -r requirements.txt
py -m uvicorn main:app --reload
```

If your computer uses `python` instead of `py`, run:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

The backend runs at:

```text
http://localhost:8000
```

## STEP 12: Open API Docs

Open:

```text
http://localhost:8000/docs
```

Test the `POST /chat` endpoint with:

```json
{
  "message": "Show PDF files modified yesterday",
  "session_id": "demo"
}
```

## STEP 13: Run Frontend

Open a second terminal in the project root, then run:

```powershell
cd frontend
py -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

If your computer uses `python` instead of `py`, run:

```powershell
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

## STEP 14: Open Frontend

Open:

```text
http://localhost:8501
```

Try:

```text
Find financial report from last week
```

Then try a follow-up:

```text
Only PDFs
```

## STEP 15: GitHub Push

Create a GitHub repository named:

```text
TailorTalk-Drive-Agent
```

Then run:

```powershell
git init
git add .
git commit -m "Initial TailorTalk Drive Agent project"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/TailorTalk-Drive-Agent.git
git push -u origin main
```

Before pushing, confirm this file is not included:

```text
backend/service-account.json
```

## STEP 16: Deploy Backend on Render/Railway

### Render

1. Go to <https://render.com/>.
2. Create a new Web Service.
3. Connect your GitHub repository.
4. Set the root directory to:

```text
backend
```

5. Build command:

```text
pip install -r requirements.txt
```

6. Start command:

```text
uvicorn main:app --host 0.0.0.0 --port $PORT
```

7. Add environment variables:

```env
GEMINI_API_KEY=your_real_gemini_api_key
GOOGLE_SERVICE_ACCOUNT_FILE=service-account.json
GEMINI_MODEL=gemini-2.5-flash
```

8. Add your service account JSON as a secret file if the platform supports secret files. If it does not, use the platform's documented secret-file approach.

### Railway

1. Go to <https://railway.app/>.
2. Create a new project from GitHub.
3. Set the service root to `backend`.
4. Use this start command:

```text
uvicorn main:app --host 0.0.0.0 --port $PORT
```

5. Add the same environment variables.

## STEP 17: Deploy Frontend on Streamlit Cloud

1. Go to <https://share.streamlit.io/>.
2. Create a new app from your GitHub repository.
3. Set the main file path:

```text
frontend/streamlit_app.py
```

4. Add this environment variable in Streamlit secrets or app settings:

```env
TAILORTALK_BACKEND_URL=https://your-backend-url.example.com
```

5. Deploy the app.

## STEP 18: Final Testing Checklist

Backend:

- `GET /health` returns `{"status":"ok"}`.
- `POST /chat` accepts a message and returns an answer.
- Invalid empty messages return a validation error.
- Missing `GEMINI_API_KEY` gives a clear backend error.
- Missing `GOOGLE_SERVICE_ACCOUNT_FILE` gives a clear backend error.

Google Drive:

- The folder is shared with the service account email.
- Exact file name search works.
- Partial file name search works.
- `fullText contains` search works for indexed Drive content.
- PDF filtering works.
- Image filtering works.
- Spreadsheet filtering works.
- Created date filtering works.
- Modified date filtering works.
- Result links open in Google Drive.

Frontend:

- Streamlit opens at `http://localhost:8501`.
- Chat history is visible.
- Loading indicator appears while waiting.
- Backend connection errors are shown clearly.
- New chat starts a fresh session.

Deployment:

- Backend has all required environment variables.
- Frontend points to the deployed backend URL.
- Service account JSON is stored as a secret, not committed to GitHub.
- End-to-end chat works after deployment.

## How the Agent Works

1. The user sends a chat message in Streamlit.
2. Streamlit calls the FastAPI `/chat` endpoint.
3. FastAPI sends the message and session ID to the LangChain agent.
4. Gemini decides when to call `DriveSearchTool`.
5. `DriveSearchTool` creates or receives a Google Drive `q` parameter.
6. The tool calls Google Drive API `files.list()`.
7. Results are returned with file name, file type, modified date, and clickable link.
8. Gemini formats the final conversational answer.

## Important Security Notes

- Never commit `.env`.
- Never commit `service-account.json`.
- Share only the Drive folders the service account should search.
- Use Viewer access unless the app truly needs more permissions.
- Rotate the service account key if it is ever exposed.
