# Career Copilot Week 6 - Integration and Functional Test Guide

This guide assumes your working repository is:

`C:\Users\Arjun Viswanathan\OneDrive\Documents\career-copilot`

The Week 6 bundle changes the Python application, discovery logic, native C++ matcher, document generation, dependencies, tests, and documentation. The C++ module **must be rebuilt** because the pybind11 interface changed.

## 1. Protect your current working version

Open PowerShell in the current repository:

```powershell
cd "C:\Users\Arjun Viswanathan\OneDrive\Documents\career-copilot"
git status
```

Commit anything you want to keep before integration:

```powershell
git add .
git commit -m "Checkpoint before Week 6 integration"
```

Create a dedicated branch:

```powershell
git checkout -b week6-finalization
```

Optional filesystem backup:

```powershell
Copy-Item `
  "C:\Users\Arjun Viswanathan\OneDrive\Documents\career-copilot" `
  "C:\Users\Arjun Viswanathan\OneDrive\Documents\career-copilot-pre-week6" `
  -Recurse
```

## 2. Integrate the Week 6 files

If using the full Week 6 repo ZIP, extract it to a temporary directory first. Do not copy `.env`, `.venv`, or any old `cpp\build` folder from the bundle.

Replace these existing files with the Week 6 versions:

```text
app.py
candidate_profile.json
requirements.txt
README.md
.gitignore
cpp/CMakeLists.txt
cpp/match_engine.cpp
discovery/agent.py
discovery/ranking.py
```

Add these new files/folders:

```text
assets/profile_photo.jpeg
documents/__init__.py
documents/application_docs.py
Dockerfile
.dockerignore
tests/test_week6_ranking.py
tests/test_week6_discovery_stats.py
tests/test_week6_documents.py
tests/test_week6_cpp_contract.py
WEEK6_CHANGELOG.md
WEEK6_INTEGRATION_GUIDE.md
```

Keep your existing local `.env` file. Do not copy it into Git.

If you already have real application records under `data\applications`, keep them. The Week 6 source bundle does not require deleting your history.

## 3. Activate the same virtual environment used by Streamlit

```powershell
cd "C:\Users\Arjun Viswanathan\OneDrive\Documents\career-copilot"
.\.venv\Scripts\Activate.ps1
```

Verify:

```powershell
python --version
python -c "import sys; print(sys.executable)"
```

Expected for your current environment: Python 3.13.x and the executable inside `career-copilot\.venv\Scripts\python.exe`.

## 4. Update Python dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Verify pybind11:

```powershell
python -m pybind11 --cmakedir
```

## 5. Clean the old Week 5 C++ build

This step is mandatory. The Week 6 matcher now accepts required skills, preferred skills, and evidence weights, and returns richer match explanations. An old `.pyd` will not satisfy the new interface.

```powershell
cd cpp
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
New-Item -ItemType Directory build | Out-Null
cd build
```

Configure CMake using the active Python environment:

```powershell
$pythonExe = (Get-Command python).Source
$pybindDir = (python -m pybind11 --cmakedir).Trim('"')

Test-Path "$pybindDir\pybind11Config.cmake"
```

The final command should print `True`.

Configure:

```powershell
cmake .. "-Dpybind11_DIR=$pybindDir" "-DPython_EXECUTABLE=$pythonExe"
```

Build:

```powershell
cmake --build . --config Release
```

Confirm the extension exists:

```powershell
Get-ChildItem -Recurse -Filter "match_engine*.pyd"
```

Return to the project root:

```powershell
cd ..\..
```

## 6. Test the native C++ module directly

```powershell
python -c "import sys; sys.path.insert(0, r'cpp\build\Release'); import match_engine; print('MATCH ENGINE:', match_engine.__file__)"
```

Then test the new Week 6 function contract:

```powershell
python -c "import sys; sys.path.insert(0, r'cpp\build\Release'); import match_engine; r=match_engine.calculate_match(['C++20','ISO 26262 (ASIL-D)','System Integration'],['C++','ISO26262','Software Integration'],[],{'C++20':1.0,'ISO 26262 (ASIL-D)':1.0,'System Integration':1.0}); print(r.score, r.matched_skills, r.related_skills, r.missing_skills)"
```

You should see a strong score, exact/alias matches for C++ and ISO 26262, and related evidence for system/software integration.

## 7. Run deterministic Week 6 tests

```powershell
python -m pytest `
  tests/test_week6_ranking.py `
  tests/test_week6_discovery_stats.py `
  tests/test_week6_documents.py `
  tests/test_week6_cpp_contract.py `
  -v
```

The C++ contract test should run now that the module is built.

Then run the existing deterministic tests:

```powershell
python -m pytest tests/test_filters.py tests/test_ranking.py -v
```

## 8. Run the complete regression suite

```powershell
python -m pytest tests -v
```

Important: existing Jooble/Arbeitnow/BA integration tests depend on external services, credentials and network availability. A source/network failure must be distinguished from a deterministic code failure.

## 9. Launch Career Copilot

Always launch through the same Python interpreter:

```powershell
python -m streamlit run app.py
```

Do not use a different global `streamlit.exe` for this test.

## 10. Functional test - Candidate Profile

1. Open `Candidate Profile`.
2. Choose `Load existing profile`.
3. Load `candidate_profile.json`.
4. Confirm the profile validates.
5. Confirm the new contact/language/publication/certification information is present in the structured JSON.
6. Save the profile once and confirm the app remains stable.

Pass condition: the approved candidate profile loads without invalidating downstream state unexpectedly.

## 11. Functional test - Job Discovery

Use a representative search such as:

```text
Keyword: Embedded Software Engineer
Cities: Stuttgart, Munich, Frankfurt
Radius: 50 km
Minimum target salary: €80,000
Sources: Jooble, Arbeitnow, Bundesagentur
```

Check:

- jobs are ranked;
- Initial Fit is no longer implausibly low for relevant embedded roles;
- each result shows a Technical / Title / Seniority / Domain breakdown;
- `Discovery Source Health` distinguishes zero-result sources from failed sources;
- unknown salary is still shown as unknown and is not falsely presented as employer-published;
- a source failure does not crash the complete discovery run.

## 12. Functional test - Shortlist and automatic analysis

Choose one relevant job and click `Shortlist for Analysis`.

Expected behavior:

1. Message shows that the detailed job description is being retrieved.
2. Career Copilot attempts the employer/company vacancy page.
3. If employer extraction works, the detailed description is stored.
4. If the site blocks automation, the best source description remains as an explicitly labelled fallback.
5. The app switches to `Job Analysis`.
6. `Job is being analysed` / equivalent transfer status is displayed.
7. AI JobProfile extraction runs automatically when a reliable employer description was obtained; otherwise the description remains available for manual review/analysis.

## 13. Functional test - Week 6 C++ compatibility

In Job Analysis verify:

- compatibility score appears;
- strong matches appear separately;
- related evidence appears separately;
- missing required skills appear separately;
- preferred matches do not receive the same weight as required skills;
- the `Compatibility score explanation` expander lists job skill, candidate evidence, match type and strength.

Sanity-check at least three jobs:

1. High relevance - embedded/AUTOSAR/C++.
2. Adjacent relevance - systems/simulation/controls.
3. Poor relevance - unrelated backend/software domain.

The score ordering matters more than any specific percentage.

## 14. Functional test - Complete Application Package

Open `Application Package`.

Click:

`Generate Complete Application Package`

Expected sequence:

```text
1/3 Tailoring CV
2/3 Writing cover letter
3/3 Preparing interview questions
```

Then confirm all three status cards show ready.

Also test individual regeneration for CV, cover letter and interview preparation. Individual regeneration must still work after a complete-package run.

## 15. Visually inspect the generated CV

Download the tailored CV.

Compare it with your supplied CV reference. Confirm:

- two-page professional layout where content length permits;
- large name header and photograph;
- centered Gaildorf / phone / e-mail line;
- Technical Skills section with grouped technical categories;
- Work Experience hierarchy and bullet formatting;
- Education section;
- Patents & Publications & Awards section;
- Certifications;
- Languages;
- no generic Word headings or generic template styling;
- no fabricated candidate facts.

If a specific job causes the CV to overflow to three pages, first inspect whether the AI produced overly long experience bullets. Regenerate before changing global font/layout values.

## 16. Visually inspect the generated cover letter

Download the cover letter and compare it with the supplied LOM reference.

Confirm:

- centered name/contact header;
- `To,` line;
- target company;
- bold job-specific subject;
- `Dear Hiring Team,`;
- three concise body paragraphs;
- `Sincerely` and candidate name;
- one-page layout for normal generation lengths;
- no duplicate salutation, recipient, subject or signature inside the generated AI body.

## 17. Save and reload an application

1. Save the application record.
2. Open Application History.
3. Confirm the current company, role and compatibility data appears.
4. Stop Streamlit.
5. Restart:

```powershell
python -m streamlit run app.py
```

6. Confirm persisted discovery/application data loads without crashing.

## 18. Optional Docker validation

After the local Windows build is fully stable:

```powershell
docker build -t career-copilot .
docker run --rm -p 8501:8501 --env-file .env career-copilot
```

Open:

`http://localhost:8501`

Do not spend time debugging public hosting until the local Docker image is healthy.

## 19. Final Git commit

```powershell
git status
git add .
git commit -m "Complete Week 6 Career Copilot finalization"
git push -u origin week6-finalization
```

After final functional validation you can merge into `main` according to your normal Git workflow.

## Week 6 release acceptance criteria

Week 6 is complete when all of the following are true:

- no P0/P1 backlog bugs remain in the main flow;
- multi-source discovery fails gracefully;
- discovery ranking sensibly prioritizes relevant engineering roles;
- C++ compatibility uses the rebuilt Week 6 interface and provides explainable strong/related/missing matches;
- shortlist -> detail retrieval -> Job Analysis works;
- complete application package generation works in one click;
- CV and cover letter follow the supplied reference designs;
- generated content remains factual;
- application history persists;
- deterministic tests pass;
- full regression is completed;
- README and build instructions are current;
- local run is stable; Docker is validated if deployment is part of the release target.
