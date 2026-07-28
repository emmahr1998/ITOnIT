# ITOnIT


**ITOnIT** is an IT support reporting system designed to streamline communication between employees and the IT department within an organization.

The application enables employees to quickly report hardware, software, and network-related issues through an intuitive interface instead of relying on phone calls, emails, or messaging applications. Each issue is submitted as a support ticket containing relevant details such as the problem description, category, priority, location, and optional attachments (e.g., screenshots or photos).

Once a ticket is created, the IT team can review it, assign it to an appropriate technician, update its status throughout the resolution process, and communicate with the employee when additional information is required. Employees can track the progress of their requests in real time and receive notifications whenever the ticket status changes.

ITOnIT aims to improve the efficiency of IT support by centralizing all support requests in one system, increasing transparency, reducing response times, and providing better organization and tracking of technical issues from submission to resolution.

## API Endpoints :

### Health

| Method | Endpoint | Description |
|:------:|----------|-------------|
| GET | `/health` | Check the health status of the application. |

---

### Authentication

| Method | Endpoint | Description |
|:------:|----------|-------------|
| POST | `/auth/login` | Authenticate a user and return access and refresh JWT tokens. |
| POST | `/auth/refresh` | Generate a new access token using a valid refresh token. |
| GET | `/auth/me` | Retrieve the currently authenticated user's information. |

---

### Categories

| Method | Endpoint | Description |
|:------:|----------|-------------|
| GET | `/categories` | Retrieve all categories. |
| POST | `/categories` | Create a new category. |
| GET | `/categories/{category_id}` | Retrieve a category by its ID. |
| PUT | `/categories/{category_id}` | Update an existing category. |
| DELETE | `/categories/{category_id}` | Delete a category. |

---

### Departments

| Method | Endpoint | Description |
|:------:|----------|-------------|
| GET | `/departments` | Retrieve all departments. |
| POST | `/departments` | Create a new department. |
| GET | `/departments/{department_id}` | Retrieve a department by its ID. |
| PATCH | `/departments/{department_id}` | Update an existing department. |

---

### Priorities

| Method | Endpoint | Description |
|:------:|----------|-------------|
| GET | `/priorities` | Retrieve all ticket priorities. |
| POST | `/priorities` | Create a new priority. |
| GET | `/priorities/{priority_id}` | Retrieve a priority by its ID. |
| PATCH | `/priorities/{priority_id}` | Update an existing priority. |

---

### Users

| Method | Endpoint | Description |
|:------:|----------|-------------|
| POST | `/users` | Create a new user. |
| GET | `/users` | Retrieve all users. |
| GET | `/users/{user_id}` | Retrieve a user by ID. |
| PATCH | `/users/{user_id}` | Update user information. |
| PATCH | `/users/me/password` | Change the authenticated user's password. |
| PATCH | `/users/{user_id}/password` | Reset another user's password (Administrator only). |

---

### Tickets

| Method | Endpoint | Description |
|:------:|----------|-------------|
| POST | `/ticket-new` | Create a new support ticket. |
| GET | `/all-tickets` | Retrieve all tickets accessible to the current user. |
| GET | `/tickets/{ticket_id}` | Retrieve a ticket by ID. |
| PATCH | `/tickets/{ticket_id}` | Update ticket details. |
| DELETE | `/tickets/{ticket_id}` | Delete a ticket. |
| PATCH | `/tickets/{ticket_id}/assign` | Assign a technician to a ticket. |
| PATCH | `/tickets/{ticket_id}/status` | Update the ticket status. |

#### Comments

| Method | Endpoint | Description |
|:------:|----------|-------------|
| GET | `/tickets/{ticket_id}/comments` | Retrieve all comments for a ticket. |
| POST | `/tickets/{ticket_id}/comments` | Add a new comment to a ticket. |
| PUT | `/tickets/{ticket_id}/comments/{comment_id}` | Update an existing comment. |
| DELETE | `/tickets/{ticket_id}/comments/{comment_id}` | Delete a comment. |

#### Ticket History

| Method | Endpoint | Description |
|:------:|----------|-------------|
| GET | `/tickets/{ticket_id}/history` | Retrieve the complete history of a ticket. |

---

### Attachments

| Method | Endpoint | Description |
|:------:|----------|-------------|
| GET | `/tickets/{ticket_id}/attachments` | Retrieve all attachments for a ticket. |
| POST | `/tickets/{ticket_id}/attachments` | Upload a new attachment. |
| GET | `/tickets/{ticket_id}/attachments/{attachment_id}` | Download an attachment. |
| DELETE | `/tickets/{ticket_id}/attachments/{attachment_id}` | Delete an attachment. |
