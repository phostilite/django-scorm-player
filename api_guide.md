# SCORM Player API Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Authentication](#authentication)
3. [API Endpoints](#api-endpoints)
   - [User Management](#user-management)
   - [Course Management](#course-management)
   - [SCORM Package Management](#scorm-package-management)
   - [User Course Registration](#user-course-registration)
   - [SCORM Attempts](#scorm-attempts)
   - [SCORM API](#scorm-api)
   - [Reporting](#reporting)
4. [Error Handling](#error-handling)
5. [Rate Limiting](#rate-limiting)
6. [Changelog](#changelog)

## Introduction

This API guide provides comprehensive documentation for integrating the Optimized SCORM Player into your Learning Management System (LMS). Our SCORM player is designed to handle large numbers of concurrent users efficiently, using a log-based approach to reduce database load and improve overall system performance.

## Authentication

The SCORM Player API uses token-based authentication. To authenticate, include the token in the `Authorization` header of your HTTP requests.

```
Authorization: Token <your_token_here>
```

To obtain a token, use the following endpoint:

```
POST /api/api-token-auth/
```

Request body:
```json
{
  "username": "your_username",
  "password": "your_password"
}
```

Response:
```json
{
  "token": "your_auth_token"
}
```

## API Endpoints

### User Management

#### Create a new user

```
POST /api/users/
```

Request body:
```json
{
  "username": "newuser",
  "email": "newuser@example.com",
  "password": "securepassword",
  "first_name": "John",
  "last_name": "Doe"
}
```

Response:
```json
{
  "user": {
    "id": 1,
    "username": "newuser",
    "email": "newuser@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "token": "your_auth_token"
}
```

#### Validate a user

```
POST /api/users/validate_user/
```

Request body:
```json
{
  "username": "existinguser",
  "email": "existinguser@example.com"
}
```

Response:
```json
{
  "exists": true,
  "user_id": 1
}
```

#### List users (admin only)

```
GET /api/users/
```

#### Retrieve a specific user

```
GET /api/users/{user_id}/
```

#### Update a user

```
PUT /api/users/{user_id}/
```

#### Delete a user (admin only)

```
DELETE /api/users/{user_id}/
```

### Course Management

#### List all courses

```
GET /api/courses/
```

#### Create a new course

```
POST /api/courses/
```

Request body:
```json
{
  "title": "Introduction to SCORM",
  "description": "Learn the basics of SCORM packaging and implementation",
  "is_active": true
}
```

#### Retrieve a specific course

```
GET /api/courses/{course_id}/
```

#### Update a course

```
PUT /api/courses/{course_id}/
```

#### Delete a course

```
DELETE /api/courses/{course_id}/
```

### SCORM Package Management

#### List all SCORM packages

```
GET /api/scorm-packages/
```

#### Upload a new SCORM package

```
POST /api/scorm-packages/upload_package/
```

Request body (form-data):
```
course_id: 1
file: [SCORM package zip file]
```

Response:
```json
{
  "package": {
    "id": 1,
    "course": 1,
    "scorm_standard": "SCORM 1.2",
    "file": "/media/scorm_packages/package.zip",
    "version": "1.0",
    "manifest_path": "imsmanifest.xml",
    "launch_path": "index.html",
    "status": "processing",
    "uploaded_at": "2023-08-24T12:00:00Z",
    "created_at": "2023-08-24T12:00:00Z"
  },
  "task_id": "12345678-1234-5678-1234-567812345678"
}
```

#### Check SCORM package processing status

```
GET /api/scorm-packages/check_status/?task_id={task_id}
```

Response (processing):
```json
{
  "status": "processing"
}
```

Response (completed):
```json
{
  "id": 1,
  "course": 1,
  "scorm_standard": "SCORM 1.2",
  "file": "/media/scorm_packages/package.zip",
  "version": "1.0",
  "manifest_path": "imsmanifest.xml",
  "launch_path": "index.html",
  "status": "ready",
  "uploaded_at": "2023-08-24T12:00:00Z",
  "created_at": "2023-08-24T12:00:00Z"
}
```

#### Retrieve a specific SCORM package

```
GET /api/scorm-packages/{package_id}/
```

#### Delete a SCORM package

```
DELETE /api/scorm-packages/{package_id}/
```

### User Course Registration

#### Register a user for a course

```
POST /api/registrations/register_for_course/
```

Request body:
```json
{
  "user_id": 1,
  "course_id": 1
}
```

Response:
```json
{
  "id": 1,
  "user": 1,
  "course": 1,
  "registered_at": "2023-08-24T12:00:00Z"
}
```

### SCORM Attempts

#### Start a new SCORM attempt

```
POST /api/attempts/start_attempt/
```

Request body:
```json
{
  "user_id": 1,
  "package_id": 1
}
```

Response:
```json
{
  "id": 1,
  "user": 1,
  "scorm_package": 1,
  "started_at": "2023-08-24T12:00:00Z",
  "last_accessed_at": "2023-08-24T12:00:00Z",
  "completion_status": "",
  "success_status": "",
  "score": null,
  "is_complete": false
}
```

#### Update SCORM attempt progress

```
POST /api/attempts/{attempt_id}/update_progress/
```

Request body:
```json
{
  "completion_status": "completed",
  "success_status": "passed",
  "score": 85.5
}
```

#### Start a SCORM session

```
POST /api/attempts/{attempt_id}/start_session/
```

#### End a SCORM session

```
POST /api/attempts/{attempt_id}/end_session/
```

### SCORM API

#### Set a SCORM element value

```
POST /api/scorm-api/set_value/
```

Request body:
```json
{
  "attempt_id": 1,
  "element_id": "cmi.core.lesson_status",
  "value": "completed"
}
```

#### Get a SCORM element value

```
GET /api/scorm-api/get_value/?attempt_id=1&element_id=cmi.core.lesson_status
```

Response:
```json
{
  "value": "completed"
}
```

### Reporting

#### Generate user course report

```
GET /api/reports/user_course_report/?user_id=1&course_id=1
```

Response:
```json
{
  "user": {
    "id": 1,
    "username": "learner",
    "email": "learner@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "course": {
    "id": 1,
    "title": "Introduction to SCORM",
    "description": "Learn the basics of SCORM packaging and implementation",
    "created_at": "2023-08-24T12:00:00Z",
    "is_active": true
  },
  "attempts": [
    {
      "id": 1,
      "scorm_package": 1,
      "started_at": "2023-08-24T12:00:00Z",
      "last_accessed_at": "2023-08-24T13:00:00Z",
      "completion_status": "completed",
      "success_status": "passed",
      "score": 85.5,
      "is_complete": true
    }
  ]
}
```

## Error Handling

The API uses standard HTTP status codes to indicate the success or failure of requests. In case of an error, the response will include a JSON object with an `error` field describing the issue.

Example error response:

```json
{
  "error": "Invalid input. Please check your request and try again."
}
```

Common status codes:

- 200 OK: The request was successful
- 201 Created: A new resource was successfully created
- 400 Bad Request: The request was invalid or cannot be served
- 401 Unauthorized: Authentication failed or user doesn't have permissions for the requested operation
- 404 Not Found: The requested resource could not be found
- 500 Internal Server Error: The server encountered an unexpected condition that prevented it from fulfilling the request

## Rate Limiting

To ensure fair usage and protect the system from abuse, rate limiting is implemented on all API endpoints. The current rate limit is:

- 100 requests per minute per IP address

If you exceed the rate limit, you'll receive a 429 Too Many Requests response. The response will include a `Retry-After` header indicating the number of seconds to wait before making another request.

## Changelog

### Version 1.0.0 (2023-08-24)

- Initial release of the SCORM Player API
- Implemented user management, course management, and SCORM package management
- Added SCORM attempt tracking and reporting features
- Introduced log-based SCORM interaction capture for improved performance

---

This API documentation is subject to change. Please check regularly for updates and new features.