# Career Copilot

Career Copilot is an AI-assisted job-search and application system for engineering roles in Germany. It combines structured CV parsing, multi-source job discovery, explainable ranking, a native C++ compatibility engine exposed through pybind11, job-specific document generation, interview preparation, and local application history.

## What the project solves

A normal job-search workflow repeatedly requires the same manual steps: finding relevant vacancies, checking location and salary plausibility, comparing requirements against a CV, rewriting application documents, and keeping track of applications. Career Copilot turns those steps into one auditable pipeline while keeping the approved candidate profile as the factual source of truth.

## End-to-end flow

```text
CV / approved profile
        |
        v
CandidateProfile
        |
        +------------------------------+
        |                              |
        v                              |
Jooble / Arbeitnow / BA                |
        |                              |
        v                              |
Discovery Agent                        |
        |                              |
Germany + radius + company + salary    |
        |                              |
        v                              |
Explainable Discovery Ranking          |
        |                              |
        v                              |
Selected vacancy -> company detail retrieval
        |
        v
Structured JobProfile
        |
        v
C++20 Compatibility Engine (pybind11)
        |
        v
Application Package
  |          |              |
  v          v              v
Tailored CV  Cover Letter   Interview Prep
        |
        v
Application History
```

## Week 6 release highlights

- One-click **Generate Complete Application Package** workflow.
- Improved discovery candidate-fit ranking using technical relevance, role/title relevance, seniority, and domain relevance.
- Per-source discovery diagnostics showing retrieval, approval, filtering, and source failures.
- Refined C++ matcher with normalization, aliases, conservative related-skill matching, preferred-skill weighting, evidence weighting, and explainable match details.
- Tailored CV generation designed around the supplied two-page CV format rather than a generic Word document.
- Cover-letter DOCX generation designed around the supplied LOM layout.
- Stronger generation prompts focused on factual, technical, role-specific language with no fabricated experience.
- Existing shortlist -> company-detail -> automatic Job Analysis workflow retained and integrated.
- Docker build added for a repeatable deployment path including the native C++ module.

## Technology stack

- Python 3.13
- Streamlit
- OpenAI API
- Pydantic
- C++20
- pybind11
- CMake
- PyMuPDF
- python-docx
- BeautifulSoup / Requests
- pandas
- pytest

## Project structure

```text
career-copilot/
├── app.py
├── candidate_profile.json
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── assets/
│   └── profile_photo.jpeg
├── cpp/
│   ├── CMakeLists.txt
│   └── match_engine.cpp
├── discovery/
│   ├── agent.py
│   ├── filters.py
│   ├── geography.py
│   ├── ranking.py
│   └── salary.py
├── documents/
│   └── application_docs.py
├── scrapers/
│   ├── base.py
│   ├── models.py
│   ├── details/
│   │   └── company_job_details.py
│   └── sources/
│       ├── jooble.py
│       ├── arbeitnow.py
│       └── ba_jobs.py
├── storage/
│   └── discovered_jobs.py
├── data/
│   ├── discovered_jobs.json
│   └── applications/
└── tests/
```

## Configuration

Create a local `.env` file. Do not commit it.

```env
OPENAI_API_KEY=...
JOOBLE_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```

Only add credentials required by the job sources you enable.

## Install

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Build the C++ match engine

The native module must be compiled for the **same Python interpreter** that runs Streamlit.

```powershell
cd cpp
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
New-Item -ItemType Directory build | Out-Null
cd build

$pythonExe = (Get-Command python).Source
$pybindDir = (python -m pybind11 --cmakedir).Trim('"')

cmake .. "-Dpybind11_DIR=$pybindDir" "-DPython_EXECUTABLE=$pythonExe"
cmake --build . --config Release
cd ..\..
```

Verify:

```powershell
Get-ChildItem -Path . -Recurse -Filter "match_engine*.pyd"
python -c "import sys; sys.path.insert(0, r'cpp\build\Release'); import match_engine; print(match_engine.__file__)"
```

After Week 6 the matcher interface changed, so an old Week 5 `.pyd` must be rebuilt.

## Run

Always launch Streamlit through the active Python interpreter:

```powershell
python -m streamlit run app.py
```

## Discovery ranking

The discovery layer is a pre-screen, not the final compatibility decision.

Initial candidate fit uses:

- Technical relevance: 45%
- Role/title relevance: 25%
- Experience/seniority: 15%
- Domain relevance: 15%

The overall Discovery Score keeps the existing Week 5 priorities:

- Location: 25%
- Company size: 20%
- Salary likelihood: 30%
- Initial candidate fit: 25%

Unknown salary is intentionally not treated as a published salary and is not automatically rejected.

## C++ compatibility engine

The C++ matcher is downstream of AI job parsing. It evaluates structured required and preferred skills against candidate evidence. Week 6 adds:

- normalization of common spelling/punctuation variants;
- alias matching such as `C++20 -> C++` and `ISO26262 -> ISO 26262`;
- conservative related-skill families;
- source-aware evidence confidence;
- lower weighting for preferred vs required skills;
- strong, related, and missing-skill explanations.

The system deliberately remains conservative: related experience contributes partial credit but does not become an invented exact skill.

## Application documents

The candidate profile remains the factual source of truth. The AI may reorder or rewrite supported content, but it is instructed not to invent experience, technologies, employers, achievements, or certifications.

The Week 6 DOCX renderer uses the supplied CV/LOM reference designs as deterministic formatting specifications. CV content is laid out using the same major section structure and a two-page professional format. The cover letter uses the same one-page hierarchy: name/contact header, recipient, subject, salutation, three body paragraphs, and signature.

## Tests

Run deterministic unit tests first:

```powershell
python -m pytest tests/test_week6_ranking.py tests/test_week6_discovery_stats.py tests/test_week6_documents.py -v
```

Then run the complete suite:

```powershell
python -m pytest tests -v
```

Some existing source tests contact live external services and therefore depend on network availability and credentials.

## Docker

Build:

```powershell
docker build -t career-copilot .
```

Run with environment variables supplied securely:

```powershell
docker run --rm -p 8501:8501 --env-file .env career-copilot
```

Open `http://localhost:8501`.

## Recommended final regression

1. Load `candidate_profile.json`.
2. Discover an embedded/software role.
3. Confirm source diagnostics and ranking explanation.
4. Shortlist the vacancy.
5. Confirm employer-detail retrieval or an honest fallback message.
6. Confirm automatic navigation to Job Analysis.
7. Verify the rebuilt Week 6 C++ compatibility result.
8. Generate the complete application package.
9. Download and visually inspect the CV and cover letter.
10. Save the application and verify Application History.
11. Restart Streamlit and check persistence.

## Known limitations

- Some job boards and company sites block automated detail-page retrieval; the application falls back to the best available source description and labels the limitation.
- Salary is frequently unpublished. Unknown salary is kept distinct from estimated or employer-published compensation.
- Company size can be unknown when a source does not expose sufficient metadata.
- The C++ matcher uses curated aliases and conservative similarity logic rather than a learned semantic model.
- External APIs can be unavailable or rate-limited; discovery is designed so one source failure does not abort the whole run.

## Future extensions

Possible post-v1 improvements include richer employer research, database-backed multi-user application history, learned ranking calibration, stronger salary estimation, authentication, and additional job sources.
