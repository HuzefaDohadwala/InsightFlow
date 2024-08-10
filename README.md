
# InsightFlow


Insight Flow is a web-based generative AI application that streamlines the process of generating product analysis review reports in just a few clicks. It serves as an analysis pipeline, taking in user-uploaded data and providing detailed insights.



## Features


- CSV File Categorization: Allows users to upload a CSV file, which gets automatically categorized into predefined categories.

- Advanced Product Review Analysis: Enables users to analyze product reviews by selecting specific criteria, generating a detailed report that can be downloaded locally.

- Interactive Report Insights: Provides users the ability to interact with the generated report via chat, allowing them to gain additional insights.

- Database Management: Includes a feature that simplifies database management, allowing users (including admins and selected users) to view and edit the database directly on the screen, without the need to access the terminal.



## Environment Variables

To run this project, you will need to add the following environment variables to your .env file

`FLASK_SECRET_KEY`

`MYSQL_HOST`

`MYSQL_USER`

`MYSQL_PASSWORD`

`MYSQL_DB`

`GROQ_API_KEY`



## Run Locally

Clone the project

```bash
  git clone https://github.com/HuzefaDohadwala/InsightFlow.git
```

Go to the project directory

```bash
  cd analysispipeline
```

Install dependencies

```bash
  !pip install requirements 
```

Start the server

```bash
  flask --app main --debug run
```



