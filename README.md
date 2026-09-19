# 🔎 Smart Lost & Found Management System

An AI/ML-based web application that helps users report, search, and recover lost and found items through intelligent item matching and secure in-app communication.

## 📌 Project Overview

The Smart Lost & Found Management System provides a centralized platform where users can:

- Report lost items
- Report found items
- Search for reported items
- Find potential matches using AI/ML
- Contact the owner or finder through private in-app messaging
- Send and receive messages related to an item
- Request case resolution after successful recovery

The system uses **Natural Language Processing (NLP)** techniques to compare item details and calculate a similarity score between lost and found reports.

---

## 🎯 Problem Statement

Traditional lost-and-found processes are often manual and inefficient. Users may have difficulty finding matching lost or found items and contacting the correct person.

This project provides a digital solution that combines:

- Centralized item reporting
- Search functionality
- AI-based matching
- Private communication
- Case resolution management

---

## ✨ Key Features

### 👤 User Authentication

- User registration and login
- Secure password hashing
- Role-based access
- User dashboard

### 📋 Lost & Found Reporting

Users can report:

- Lost items
- Found items

Each report can contain:

- Item name
- Category
- Description
- Location
- Date
- Image

### 🔍 Item Search

Users can search reported items using available item information and filters.

### 🤖 AI/ML-Based Matching

The system compares lost and found item information using:

**TF-IDF (Term Frequency–Inverse Document Frequency)**

and

**Cosine Similarity**

The system generates a similarity percentage to identify potential matches.

Example:

```text
Similarity Score: 68.52%
Match Level: Possible Match
```

---

## 🛠️ Technologies Used

| Technology | Purpose |
|---|---|
| Python | Application development |
| Streamlit | Web application interface |
| SQLite | Database management |
| Scikit-learn | Machine learning / NLP |
| TF-IDF | Text vectorization |
| Cosine Similarity | Item matching |
| Pandas | Data processing |
| Plotly | Data visualization |
| HTML/CSS | UI styling |
| Git & GitHub | Version control |

---

## 🗂️ Project Structure

```text
Smart-Lost-Found/
│
├── app.py
├── auth.py
├── database.py
├── matching.py
├── README.md
├── .gitignore
│
├── pages/
├── assets/
└── uploads/
```

> Private files such as `.env`, local databases, and uploaded files are excluded from GitHub using `.gitignore`.

---

## 🔄 System Workflow

```text
User Registration / Login
          ↓
       Dashboard
          ↓
 ┌────────┴────────┐
 ↓                 ↓
Report Lost     Report Found
 ↓                 ↓
       Database
          ↓
    Search Items
          ↓
    AI/ML Matching
          ↓
 Similarity Score
          ↓
 Potential Match
          ↓
   Contact Owner/Finder
          ↓
  Private Messaging
          ↓
   Item Recovered
          ↓
   Case Resolution
```

---

## ▶️ How to Run the Project

### 1. Clone the Repository

```bash
git clone https://github.com/ChandrashekharKumar765/Smart-Lost-Found.git
```

### 2. Open the Project

```bash
cd Smart-Lost-Found
```

### 3. Install Required Libraries

```bash
pip install streamlit pandas plotly scikit-learn
```

### 4. Run the Application

```bash
python -m streamlit run app.py
```

The application will open in your browser.

---

## 🔐 Security

The project includes basic security practices such as:

- Password hashing
- Role-based access
- Private in-app messaging
- `.env` exclusion through `.gitignore`
- Local database exclusion from GitHub
- Uploaded files excluded from GitHub

---

## 🚀 Future Enhancements

Possible future improvements include:

- Image-based item matching using computer vision
- Advanced NLP semantic similarity using transformer models
- Email notifications
- Mobile application
- GPS/location-based matching
- QR-based item identification
- Improved fraud detection
- Cloud database integration
- Cloud deployment

---

## 🎓 Project Information

**Project Type:** Academic Minor Project

**Domain:** Artificial Intelligence / Machine Learning / Web Application

**Project Name:** Smart Lost & Found Management System

---

## 👨‍💻 Author

**Chandrashekhar Kumar**

GitHub:  
https://github.com/ChandrashekharKumar765

---

## 📄 License

This project is developed for academic and educational purposes.