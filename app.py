import json
import os
from io import BytesIO
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
import match_engine
import fitz
import streamlit as st
from docx import Document
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field
from pathlib import Path



load_dotenv()


class EmploymentEntry(BaseModel):
    company: str
    role: str
    start_date: str
    end_date: str
    responsibilities: list[str]
    achievements: list[str]
    technologies: list[str]


class EducationEntry(BaseModel):
    institution: str
    degree: str
    field_of_study: str
    start_date: str
    end_date: str


class CandidateProfile(BaseModel):
    full_name: str
    professional_title: str
    professional_summary: str

    technical_skills: list[str]
    programming_languages: list[str]
    tools: list[str]
    methodologies: list[str]
    industries: list[str]

    employment_history: list[EmploymentEntry]
    education: list[EducationEntry]

    certifications: list[str]
    spoken_languages: list[str]
    leadership_experience: list[str]
    achievements: list[str]


class JobProfile(BaseModel):
    job_title: str
    company: str
    location: str

    required_skills: list[str]
    preferred_skills: list[str]

    required_experience_years: float

    education_requirements: list[str]
    language_requirements: list[str]

    responsibilities: list[str]

    industry: str
    seniority: str

class TailoredExperience(BaseModel):
    company: str
    job_title: str
    bullets: list[str]


class TailoredCV(BaseModel):
    professional_title: str
    professional_summary: str

    prioritized_skills: list[str]

    experience: list[
        TailoredExperience
    ]

    education: list[str]

    certifications: list[str]

class InterviewQuestion(BaseModel):
    question: str
    category: str
    why_it_matters: str
    preparation_points: list[str]


class InterviewPreparation(BaseModel):
    technical_questions: list[
        InterviewQuestion
    ]

    behavioral_questions: list[
        InterviewQuestion
    ]

    experience_questions: list[
        InterviewQuestion
    ]    

class ApplicationPackage(BaseModel):
    tailored_cv: TailoredCV
    cover_letter: str
    interview_preparation: (
        InterviewPreparation
    )

def extract_pdf_text(file_bytes: bytes) -> str:
    document = fitz.open(
        stream=file_bytes,
        filetype="pdf",
    )

    pages: list[str] = []

    for page in document:
        text = page.get_text("text")

        if text.strip():
            pages.append(text)

    document.close()

    return "\n".join(pages)


def extract_docx_text(file_bytes: bytes) -> str:
    document = Document(BytesIO(file_bytes))

    paragraphs = [
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]

    return "\n".join(paragraphs)


def extract_cv_text(
    filename: str,
    file_bytes: bytes,
) -> str:
    lower_filename = filename.lower()

    if lower_filename.endswith(".pdf"):
        return extract_pdf_text(file_bytes)

    if lower_filename.endswith(".docx"):
        return extract_docx_text(file_bytes)

    raise ValueError(
        "Unsupported file type. Upload a PDF or DOCX file."
    )


def create_candidate_profile(
    cv_text: str,
) -> CandidateProfile:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY was not found in the .env file."
        )

    client = OpenAI(api_key=api_key)

    system_prompt = """
You are a precise CV information-extraction system.

Extract only information explicitly supported by the supplied CV.

Rules:
1. Never invent experience, skills, qualifications or achievements.
2. Preserve company names, role names and dates as written.
3. When information is unavailable, use an empty string or empty list.
4. Do not evaluate whether the candidate is good or bad.
5. Do not improve or rewrite the candidate's experience.
6. Do not calculate information that cannot be confirmed.
7. Keep responsibilities and achievements separate where possible.
8. Return information according to the supplied structure.
"""

    response = client.responses.parse(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": (
                    "Extract a candidate profile from this CV:\n\n"
                    + cv_text
                ),
            },
        ],
        text_format=CandidateProfile,
    )

    profile = response.output_parsed

    if profile is None:
        raise ValueError(
            "The AI did not return a valid candidate profile."
        )

    return profile
def create_job_profile(
    job_description: str,
) -> JobProfile:

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY was not found."
        )

    client = OpenAI(
        api_key=api_key
    )

    system_prompt = """
You are a job-description information extraction system.

Extract structured information from the supplied job advertisement.

Rules:

1. Extract only information supported by the job description.
2. Do not invent requirements.
3. Separate required skills from preferred skills.
4. If years of experience are not explicitly stated, use 0.
5. If company, location, industry or seniority cannot be identified,
   use an empty string.
6. Keep skill names concise.
7. Preserve important technical terminology.
8. Return information according to the provided schema.
"""

    response = client.responses.parse(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": (
                    "Extract a structured job profile "
                    "from the following job advertisement:\n\n"
                    + job_description
                ),
            },
        ],
        text_format=JobProfile,
    )

    job_profile = response.output_parsed

    if job_profile is None:
        raise ValueError(
            "The AI did not return a valid job profile."
        )

    return job_profile

def normalize_skill(
    skill: str
) -> str:

    return (
        skill
        .strip()
        .lower()
    )

def calculate_match_python(
    candidate_skills: list[str],
    required_skills: list[str],
):

    candidate_set = {
        normalize_skill(skill)
        for skill in candidate_skills
    }

    matched = []
    missing = []

    for skill in required_skills:

        normalized_skill = normalize_skill(
            skill
        )

        if normalized_skill in candidate_set:

            matched.append(skill)

        else:

            missing.append(skill)

    if not required_skills:

        score = 0.0

    else:

        score = (
            len(matched)
            / len(required_skills)
        ) * 100

    return {
        "score": round(score, 1),
        "matched_skills": matched,
        "missing_skills": missing,
    }

def load_candidate_profile():

    profile_path = Path(
        "candidate_profile.json"
    )

    if not profile_path.exists():

        raise FileNotFoundError(
            "candidate_profile.json was not found."
        )

    with open(
        profile_path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)
    
def create_tailored_cv(
    candidate_data: dict,
    job_data: dict,
    match_data: dict,
) -> TailoredCV:

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY was not found."
        )

    client = OpenAI(
        api_key=api_key
    )

    system_prompt = """
You are the CV tailoring component of Career Copilot.

Your task is to create a job-specific CV using ONLY
facts contained in the approved candidate profile.

You may:
- prioritize relevant experience
- reorder skills according to job relevance
- rewrite existing experience more clearly
- shorten less relevant content
- emphasize evidence that supports the job requirements

You must NEVER:
- invent skills
- invent employers
- invent projects
- invent responsibilities
- invent certifications
- invent achievements
- claim experience merely because the job requires it

The approved candidate profile is the factual source of truth.

The compatibility analysis is guidance only.
If a skill appears in the missing-skills list,
do not claim that the candidate has that skill.

Return the tailored CV according to the provided schema.
"""

    user_content = f"""
APPROVED CANDIDATE PROFILE:

{json.dumps(candidate_data, indent=2)}

STRUCTURED JOB PROFILE:

{json.dumps(job_data, indent=2)}

COMPATIBILITY ANALYSIS:

{json.dumps(match_data, indent=2)}

Create a tailored CV for this job.
"""

    response = client.responses.parse(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
        text_format=TailoredCV,
    )

    tailored_cv = response.output_parsed

    if tailored_cv is None:
        raise ValueError(
            "The AI did not return a valid tailored CV."
        )

    return tailored_cv  
  
def create_cover_letter(
    candidate_data: dict,
    job_data: dict,
    match_data: dict,
) -> str:

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY was not found."
        )

    client = OpenAI(
        api_key=api_key
    )

    system_prompt = """
You are the cover-letter generation component
of Career Copilot.

Create a concise and professional cover letter
for the supplied job.

Rules:

1. Use only facts supported by the approved candidate profile.
2. Never invent experience, skills, achievements,
   certifications or responsibilities.
3. Focus on the strongest genuine overlap between
   the candidate and the job requirements.
4. Use the compatibility analysis to identify
   matched strengths.
5. Do not claim missing skills.
6. Avoid generic wording where possible.
7. Keep the letter approximately 300–450 words.
8. Make the tone professional and confident.
"""

    user_content = f"""
APPROVED CANDIDATE PROFILE:

{json.dumps(candidate_data, indent=2)}

JOB PROFILE:

{json.dumps(job_data, indent=2)}

COMPATIBILITY ANALYSIS:

{json.dumps(match_data, indent=2)}

Write the cover letter.
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
    )

    cover_letter = response.output_text

    if not cover_letter:
        raise ValueError(
            "No cover letter was returned."
        )

    return cover_letter

def create_interview_preparation(
    candidate_data: dict,
    job_data: dict,
    match_data: dict,
) -> InterviewPreparation:

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY was not found."
        )

    client = OpenAI(
        api_key=api_key
    )

    system_prompt = """
You are the interview-preparation component
of Career Copilot.

Generate interview questions specifically for
the candidate and job provided.

Create:

- 5 technical questions
- 5 experience-based questions
- 5 behavioral questions

For every question provide:

- the question
- its category
- why the interviewer may ask it
- preparation points

Important rules:

1. Base questions on the actual job requirements.
2. Use candidate experience where relevant.
3. Pay special attention to missing skills,
   because interviewers may probe these gaps.
4. Do not invent experience.
5. If a missing skill is important, explain that the
   candidate should prepare the theory rather than
   falsely claim experience.
6. Keep preparation advice concise and practical.
"""

    user_content = f"""
CANDIDATE PROFILE:

{json.dumps(candidate_data, indent=2)}

JOB PROFILE:

{json.dumps(job_data, indent=2)}

COMPATIBILITY ANALYSIS:

{json.dumps(match_data, indent=2)}

Generate the interview-preparation package.
"""

    response = client.responses.parse(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
        text_format=InterviewPreparation,
    )

    interview_prep = response.output_parsed

    if interview_prep is None:
        raise ValueError(
            "The AI did not return valid interview preparation."
        )

    return interview_prep

def create_cv_docx(
    cv_data: dict,
) -> bytes:

    document = Document()

    document.add_heading(
        cv_data["professional_title"],
        level=0,
    )

    document.add_heading(
        "Professional Summary",
        level=1,
    )

    document.add_paragraph(
        cv_data["professional_summary"]
    )

    document.add_heading(
        "Key Skills",
        level=1,
    )

    for skill in cv_data[
        "prioritized_skills"
    ]:
        document.add_paragraph(
            skill,
            style="List Bullet",
        )

    document.add_heading(
        "Professional Experience",
        level=1,
    )

    for experience in cv_data[
        "experience"
    ]:

        document.add_heading(
            (
                experience["job_title"]
                + " — "
                + experience["company"]
            ),
            level=2,
        )

        for bullet in experience[
            "bullets"
        ]:
            document.add_paragraph(
                bullet,
                style="List Bullet",
            )

    document.add_heading(
        "Education",
        level=1,
    )

    for item in cv_data[
        "education"
    ]:
        document.add_paragraph(
            item,
            style="List Bullet",
        )

    document.add_heading(
        "Certifications",
        level=1,
    )

    for item in cv_data[
        "certifications"
    ]:
        document.add_paragraph(
            item,
            style="List Bullet",
        )

    buffer = BytesIO()

    document.save(
        buffer
    )

    buffer.seek(0)

    return buffer.getvalue()

def create_cover_letter_docx(
    cover_letter: str,
) -> bytes:

    document = Document()

    document.add_heading(
        "Cover Letter",
        level=0,
    )

    for paragraph in cover_letter.split(
        "\n"
    ):

        if paragraph.strip():

            document.add_paragraph(
                paragraph.strip()
            )

    buffer = BytesIO()

    document.save(
        buffer
    )

    buffer.seek(0)

    return buffer.getvalue()

def create_interview_docx(
    prep: dict,
) -> bytes:

    document = Document()

    document.add_heading(
        "Interview Preparation",
        level=0,
    )

    sections = [
        (
            "Technical Questions",
            "technical_questions",
        ),
        (
            "Experience Questions",
            "experience_questions",
        ),
        (
            "Behavioral Questions",
            "behavioral_questions",
        ),
    ]

    for section_title, key in sections:

        document.add_heading(
            section_title,
            level=1,
        )

        for item in prep[key]:

            document.add_heading(
                item["question"],
                level=2,
            )

            document.add_paragraph(
                "Why this may be asked:"
            )

            document.add_paragraph(
                item["why_it_matters"]
            )

            document.add_paragraph(
                "Preparation points:"
            )

            for point in item[
                "preparation_points"
            ]:

                document.add_paragraph(
                    point,
                    style="List Bullet",
                )

    buffer = BytesIO()

    document.save(
        buffer
    )

    buffer.seek(0)

    return buffer.getvalue()

def save_application_record(
    candidate_data: dict,
    job_data: dict,
    match_data: dict,
    tailored_cv: dict | None = None,
    cover_letter: str | None = None,
    interview_prep: dict | None = None,
    status="Prepared",
):
    applications_folder = Path(
        "data/applications"
    )

    applications_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now()

    application_id = timestamp.strftime(
        "%Y%m%d_%H%M%S"
    )

    application_record = {
        "application_id": application_id,

        "created_at": timestamp.isoformat(),

        "company": job_data.get(
            "company",
            ""
        ),

        "job_title": job_data.get(
            "job_title",
            ""
        ),

        "location": job_data.get(
            "location",
            ""
        ),

        "match_score": match_data.get(
            "score",
            0
        ),

        "matched_skills": match_data.get(
            "matched_skills",
            []
        ),

        "missing_skills": match_data.get(
            "missing_skills",
            []
        ),

        "status": status,

        "candidate_profile": candidate_data,

        "job_profile": job_data,

        "tailored_cv": tailored_cv,

        "cover_letter": cover_letter,

        "interview_preparation": (
            interview_prep
        ),
    }

    file_path = (
        applications_folder
        / f"{application_id}.json"
    )

    with open(
        file_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            application_record,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return file_path

def load_application_history():
    applications_folder = Path(
        "data/applications"
    )

    if not applications_folder.exists():
        return []

    applications = []

    for file_path in (
        applications_folder.glob(
            "*.json"
        )
    ):

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(
                    file
                )

                applications.append(
                    data
                )

        except Exception:
            continue

    applications.sort(
        key=lambda item: item.get(
            "created_at",
            ""
        ),
        reverse=True,
    )

    return applications

defaults = {
    "candidate_profile": None,
    "job_profile": None,
    "cpp_result": None,
    "tailored_cv": None,
    "cover_letter": None,
    "interview_prep": None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.set_page_config(
    page_title="Career Copilot",
    page_icon="💼",
    layout="wide",
)

st.title("Career Copilot")
st.subheader("AI-powered CV profile extractor")

uploaded_file = st.file_uploader(
    "Upload your CV",
    type=["pdf", "docx"],
)

if uploaded_file is not None:
    try:
        extracted_text = extract_cv_text(
            filename=uploaded_file.name,
            file_bytes=uploaded_file.getvalue(),
        )

        if not extracted_text.strip():
            st.error(
                "No readable text was found in this document."
            )
            st.stop()

        st.success("The CV text was extracted successfully.")

        with st.expander("View extracted CV text"):
            st.text_area(
                "Extracted text",
                value=extracted_text,
                height=450,
            )

        if st.button(
            "Create candidate profile",
            type="primary",
        ):
            with st.spinner(
                "The AI is analysing the CV..."
            ):
                profile = create_candidate_profile(
                    extracted_text
                )

                st.session_state["candidate_profile"] = (
                    profile.model_dump()
                )

    except Exception as error:
        st.error(f"An error occurred: {error}")


if "candidate_profile" in st.session_state:
    st.subheader("Review your candidate profile")

    profile_data = st.session_state["candidate_profile"]

    st.warning(
        "Review the information carefully. "
        "The AI may misunderstand or omit details."
    )

    full_name = st.text_input(
        "Full name",
        value=profile_data.get("full_name", ""),
    )

    professional_title = st.text_input(
        "Professional title",
        value=profile_data.get(
            "professional_title",
            "",
        ),
    )

    professional_summary = st.text_area(
        "Professional summary",
        value=profile_data.get(
            "professional_summary",
            "",
        ),
        height=150,
    )

    technical_skills = st.text_area(
        "Technical skills — one skill per line",
        value="\n".join(
            profile_data.get(
                "technical_skills",
                [],
            )
        ),
        height=200,
    )

    programming_languages = st.text_area(
        "Programming languages — one per line",
        value="\n".join(
            profile_data.get(
                "programming_languages",
                [],
            )
        ),
        height=120,
    )

    tools = st.text_area(
        "Tools — one per line",
        value="\n".join(
            profile_data.get("tools", [])
        ),
        height=180,
    )

    methodologies = st.text_area(
        "Methodologies — one per line",
        value="\n".join(
            profile_data.get(
                "methodologies",
                [],
            )
        ),
        height=120,
    )

    industries = st.text_area(
        "Industries — one per line",
        value="\n".join(
            profile_data.get(
                "industries",
                [],
            )
        ),
        height=100,
    )

    reviewed_profile = profile_data.copy()

    reviewed_profile["full_name"] = full_name
    reviewed_profile["professional_title"] = (
        professional_title
    )
    reviewed_profile["professional_summary"] = (
        professional_summary
    )

    reviewed_profile["technical_skills"] = [
        item.strip()
        for item in technical_skills.splitlines()
        if item.strip()
    ]

    reviewed_profile["programming_languages"] = [
        item.strip()
        for item in programming_languages.splitlines()
        if item.strip()
    ]

    reviewed_profile["tools"] = [
        item.strip()
        for item in tools.splitlines()
        if item.strip()
    ]

    reviewed_profile["methodologies"] = [
        item.strip()
        for item in methodologies.splitlines()
        if item.strip()
    ]

    reviewed_profile["industries"] = [
        item.strip()
        for item in industries.splitlines()
        if item.strip()
    ]

    st.subheader("Complete structured profile")

    st.json(reviewed_profile)

    profile_json = json.dumps(
        reviewed_profile,
        indent=2,
        ensure_ascii=False,
    )

    st.download_button(
        label="Download approved candidate profile",
        data=profile_json,
        file_name="candidate_profile.json",
        mime="application/json",
        type="primary",
    )
    st.divider()

candidate_data = (
    load_candidate_profile()
)    

st.header("Job Compatibility Analysis")

st.write(
    "Paste a job description below. "
    "Career Copilot will analyse the requirements "
    "and compare them with your candidate profile."
)

job_description = st.text_area(
    "Job description",
    height=400,
    placeholder="Paste the full job advertisement here..."
)
if st.button(
    "Analyse job description",
    type="primary",
):
    if not job_description.strip():

        st.warning(
            "Please paste a job description first."
        )

    else:

        with st.spinner(
            "Career Copilot is analysing the job..."
        ):

            try:

                job_profile = create_job_profile(
                    job_description
                )

                st.session_state[
                    "job_profile"
                ] = job_profile.model_dump()

                st.success(
                    "Job description analysed successfully."
                )

            except Exception as error:

                st.error(
                    f"Job analysis failed: {error}"
                )
if "job_profile" in st.session_state:

    candidate_data = None

    try:
        candidate_data = (
            load_candidate_profile()
        )

    except FileNotFoundError:
        pass

    job_data = st.session_state["job_profile"]

    st.session_state["cpp_result"] = match_engine.calculate_match(
        candidate_data["technical_skills"],
        job_data["required_skills"],
    )

    st.session_state["match_result"] = {
        "score": st.session_state["cpp_result"].score,
        "matched_skills": list(
            st.session_state["cpp_result"].matched_skills
        ),
        "missing_skills": list(
            st.session_state["cpp_result"].missing_skills
        ),
    }

    st.subheader("C++ Compatibility Analysis")

    match_data = st.session_state["match_result"]

    st.metric(
        "Technical Match Score",
        f"{match_data['score']:.1f}%"
    )

    col1, col2 = st.columns(2)

    with col1:
        st.success("Matched Skills")

        if match_data["matched_skills"]:
            for skill in match_data["matched_skills"]:
                st.write(f"✅ {skill}")
        else:
            st.write("No exact skill matches found.")

    with col2:
        st.warning("Missing Skills")

        if match_data["missing_skills"]:
            for skill in match_data["missing_skills"]:
                st.write(f"⚠️ {skill}")
        else:
            st.write("No missing required skills.")
st.divider()

st.header(
    "Application Package"
)

candidate_ready = (
    st.session_state["candidate_profile"] is not None
)

if not candidate_ready:
    st.info("Create or load a candidate profile first.")

job_ready = (
    st.session_state["job_profile"] is not None
)

match_ready = (
    st.session_state["cpp_result"] is not None
)        
if (
    candidate_ready
    and job_ready
    and match_ready
):

    st.success(
        "Career Copilot has all "
        "inputs required to generate "
        "an application package."
    )

else:

    st.info(
        "Complete the candidate profile, "
        "job analysis, and compatibility "
        "analysis first."
    )

if (
    candidate_data is not None
    and "job_profile" in st.session_state
    and "match_result" in st.session_state
):

    if st.button(
        "Generate Tailored CV",
        type="primary",
    ):

        with st.spinner(
            "Career Copilot is tailoring your CV..."
        ):

            try:

                tailored_cv = create_tailored_cv(
                    candidate_data,
                    st.session_state["job_profile"],
                    st.session_state["match_result"],
                )

                st.session_state["tailored_cv"] = (
                    tailored_cv.model_dump()
                )

                st.success(
                    "Tailored CV generated successfully."
                )

            except Exception as error:

                st.error(
                    f"Tailored CV generation failed: {error}"
                )
if "tailored_cv" in st.session_state:

    st.subheader(
        "Tailored CV"
    )

    st.json(
        st.session_state["tailored_cv"]
    )    
if (
    candidate_data is not None
    and "job_profile" in st.session_state
    and "match_result" in st.session_state
):

    if st.button(
        "Generate Cover Letter"
    ):

        with st.spinner(
            "Career Copilot is writing the cover letter..."
        ):

            try:

                cover_letter = create_cover_letter(
                    candidate_data,
                    st.session_state["job_profile"],
                    st.session_state["match_result"],
                )

                st.session_state["cover_letter"] = (
                    cover_letter
                )

                st.success(
                    "Cover letter generated successfully."
                )

            except Exception as error:

                st.error(
                    f"Cover letter generation failed: {error}"
                )  

if "cover_letter" in st.session_state:

    st.subheader(
        "Cover Letter"
    )

    st.text_area(
        "Generated cover letter",
        value=st.session_state[
            "cover_letter"
        ],
        height=500,
    )  

if (
    candidate_data is not None
    and "job_profile" in st.session_state
    and "match_result" in st.session_state
):

    if st.button(
        "Generate Interview Preparation"
    ):

        with st.spinner(
            "Career Copilot is preparing interview questions..."
        ):

            try:

                interview_prep = (
                    create_interview_preparation(
                        candidate_data,
                        st.session_state["job_profile"],
                        st.session_state["match_result"],
                    )
                )

                st.session_state[
                    "interview_preparation"
                ] = interview_prep.model_dump()

                st.success(
                    "Interview preparation generated successfully."
                )

            except Exception as error:

                st.error(
                    f"Interview preparation failed: {error}"
                )
if (
    "interview_preparation"
    in st.session_state
):

    prep = st.session_state[
        "interview_preparation"
    ]

    st.subheader(
        "Interview Preparation"
    )

    st.markdown(
        "### Technical Questions"
    )

    for item in prep[
        "technical_questions"
    ]:

        st.markdown(
            f"**Question:** {item['question']}"
        )

        st.write(
            f"Why it matters: {item['why_it_matters']}"
        )

        st.write(
            "Preparation points:"
        )

        for point in item[
            "preparation_points"
        ]:
            st.write(
                f"- {point}"
            )

        st.divider()

if (
    "interview_preparation"
    in st.session_state
):

    prep = st.session_state[
        "interview_preparation"
    ]

    st.subheader(
        "Interview Preparation"
    )

    st.markdown(
        "### Behavioral Questions"
    )

    for item in prep[
        "behavioral_questions"
    ]:

        st.markdown(
            f"**Question:** {item['question']}"
        )

        st.write(
            f"Why it matters: {item['why_it_matters']}"
        )

        st.write(
            "Preparation points:"
        )

        for point in item[
            "preparation_points"
        ]:
            st.write(
                f"- {point}"
            )

        st.divider()   
if (
    "interview_preparation"
    in st.session_state
):

    prep = st.session_state[
        "interview_preparation"
    ]

    st.subheader(
        "Interview Preparation"
    )

    st.markdown(
        "### Experience Questions"
    )

    for item in prep[
        "experience_questions"
    ]:

        st.markdown(
            f"**Question:** {item['question']}"
        )

        st.write(
            f"Why it matters: {item['why_it_matters']}"
        )

        st.write(
            "Preparation points:"
        )

        for point in item[
            "preparation_points"
        ]:
            st.write(
                f"- {point}"
            )

        st.divider()   

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Compatibility",
        "Tailored CV",
        "Cover Letter",
        "Interview Prep",
    ]
)

with tab1:

    if "match_result" in st.session_state:

        match_data = st.session_state[
            "match_result"
        ]

        st.metric(
            "Technical Match Score",
            f"{match_data['score']:.1f}%"
        )
with tab2:

    if "tailored_cv" in st.session_state:

        cv_data = st.session_state[
            "tailored_cv"
        ]

        professional_title = (
            st.text_input(
                "Professional title",
                value=cv_data[
                    "professional_title"
                ],
            )
        )

        professional_summary = (
            st.text_area(
                "Professional summary",
                value=cv_data[
                    "professional_summary"
                ],
                height=180,
            )
        )
if "tailored_cv" in st.session_state:

    cv_docx = create_cv_docx(
        st.session_state[
            "tailored_cv"
        ]
    )

    st.download_button(
        label="Download Tailored CV",
        data=cv_docx,
        file_name="tailored_cv.docx",
        mime=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
    )         

if st.button(
    "Save CV Changes"
):

    st.session_state[
        "tailored_cv"
    ][
        "professional_title"
    ] = professional_title

    st.session_state[
        "tailored_cv"
    ][
        "professional_summary"
    ] = professional_summary

    st.success(
        "CV changes saved."
    )

with tab3:

    if "cover_letter" in st.session_state:

        edited_cover_letter = (
            st.text_area(
                "Cover Letter",
                value=st.session_state[
                    "cover_letter"
                ],
                height=600,
            )
        )
        cover_docx = (
            create_cover_letter_docx(
                st.session_state[
                    "cover_letter"
                ]
            )
        )

        st.download_button(
            "Download Cover Letter",
            data=cover_docx,
            file_name="cover_letter.docx",
            mime=(
                "application/"
                "vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )

        if st.button(
            "Save Cover Letter Changes"
        ):

            st.session_state[
                "cover_letter"
            ] = edited_cover_letter

            st.success(
                "Cover letter changes saved."
            )    

with tab4:

    if "interview_preparation" in st.session_state:

        edited_interview_preparation = (
            st.text_area(
                "Interview Preparation",
                value=st.session_state[
                    "interview_preparation"
                ],
                height=600,
            )
        )
        interview_docx = (
            create_interview_docx(
                st.session_state[
                    "interview_preparation"
                ]
            )
        )

        st.download_button(
            "Download Interview Preparation",
            data=interview_docx,
            file_name="interview_preparation.docx",
            mime=(
                "application/"
                "vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )

        if st.button(
            "Save Interview Preparation Changes"
        ):

            st.session_state[
                "interview_preparation"
            ] = edited_interview_preparation

            st.success(
                "Interview preparation changes saved."
            )
st.divider()

st.subheader(
    "Save Application"
)

application_status = st.selectbox(
    "Application status",
    [
        "Analysed",
        "Prepared",
        "Applied",
        "Interview",
        "Rejected",
        "Offer",
        "Archived",
    ]
)

if (
    candidate_data is not None
    and st.session_state.get(
        "job_profile"
    )
    and st.session_state.get(
        "match_result"
    )
):

    if st.button(
        "Save Application Record"
    ):

        try:

            saved_path = (
                save_application_record(
                    candidate_data,
                    st.session_state[
                        "job_profile"
                    ],
                    st.session_state[
                        "match_result"
                    ],
                    st.session_state.get(
                        "tailored_cv"
                    ),
                    st.session_state.get(
                        "cover_letter"
                    ),
                    st.session_state.get(
                        "interview_preparation"
                    ),
                    application_status,
                )
            )

            st.success(
                "Application saved successfully."
            )

            st.write(
                f"Saved to: {saved_path}"
            )

        except Exception as error:

            st.error(
                "The application could not be saved."
            )

            st.code(
                str(error)
            )

st.divider()

st.header(
    "Application History"
)    

applications = (
    load_application_history()
)

if not applications:

    st.info(
        "No saved applications yet."
    )

else:

    history_rows = []

    for application in applications:

        history_rows.append(
            {
                "Company": (
                    application.get(
                        "company",
                        ""
                    )
                ),

                "Position": (
                    application.get(
                        "job_title",
                        ""
                    )
                ),

                "Location": (
                    application.get(
                        "location",
                        ""
                    )
                ),

                "Match Score": (
                    application.get(
                        "match_score",
                        0
                    )
                ),

                "Status": (
                    application.get(
                        "status",
                        ""
                    )
                ),

                "Created": (
                    application.get(
                        "created_at",
                        ""
                    )
                ),
            }
        )

    history_df = pd.DataFrame(
        history_rows
    )

    st.dataframe(
        history_df,
        use_container_width=True,
    )