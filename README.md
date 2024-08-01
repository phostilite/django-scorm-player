# SCORM Player with Django

This project is an open-source SCORM player built using Django. It allows users to upload SCORM packages, generate a launch link, and play the SCORM content directly in their browser. The goal of this project is to provide a simple and effective way to integrate SCORM content into web applications, making it easy for educators, trainers, and developers to host and play SCORM courses.

## Features

- **SCORM Package Upload**: Upload SCORM files directly through the web interface.
- **Launch Link Generation**: Automatically generate a launch link for the uploaded SCORM package.
- **SCORM Player**: Play SCORM content directly in the browser by clicking the launch link.
- **User-friendly Interface**: Simple and intuitive interface for managing and playing SCORM content.

## Installation

To install and run this project locally, follow these steps:

1. **Check if Python is installed**

   Ensure Python 3.8+ is installed on your system:

   ```
   python --version
   ```

2. **Clone the repository**

   ```
   git clone https://github.com/phostilite/django-scorm-player.git
   cd django-scorm-player
   ```

3. **Create a virtual environment**

   ```
   python -m venv venv
   ```

4. **Activate the virtual environment**

   On Windows:
   ```
   venv\Scripts\activate
   ```
   On macOS/Linux:
   ```
   source venv/bin/activate
   ```

5. **Install the required packages**

   ```
   pip install -r requirements.txt
   ```

6. **Make migrations and migrate the database**

   ```
   python manage.py makemigrations
   python manage.py migrate
   ```

7. **Run the Django development server**

   ```
   python manage.py runserver
   ```

## Usage

1. Open your web browser and go to `http://127.0.0.1:8000/`.
2. Upload a SCORM file using the provided interface.
3. Once uploaded, a launch link will be generated.
4. Click the launch link to play the SCORM content.
