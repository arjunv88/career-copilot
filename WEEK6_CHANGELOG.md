# Week 6 Change Log

## Application UX
- Added one-click Complete Application Package generation.
- Added per-component readiness indicators.
- Kept independent regenerate/edit/download workflows.
- Preserved shortlist -> detail retrieval -> Job Analysis navigation.

## Discovery
- Added source-health diagnostics for retrieved/approved/filtered/error counts.
- Added explainable initial-fit breakdown.
- Refined initial fit using technical, title, seniority and domain signals.
- Preserved salary-unknown behavior and Discovery Score separation from Compatibility Score.

## C++ matcher
- Replaced strict exact-string-only matching with weighted, conservative matching.
- Added normalization and aliases.
- Added related-skill families.
- Added preferred-skill weighting.
- Added candidate-evidence weighting based on source/context.
- Added detailed match explanations.
- Kept strong/related/missing evidence separate to prevent false claims.

## Application documents
- Added deterministic CV renderer based on the supplied CV reference.
- Added the supplied profile photograph as a local document asset.
- Added grouped Technical Skills, complete Work Experience, Education, patents/publications/awards, certifications and languages.
- Added deterministic one-page cover-letter renderer based on the supplied LOM reference.
- Strengthened AI prompts to reduce generic language and prohibit unsupported claims.

## Data model
- Added optional contact fields, patents, publications and awards to CandidateProfile.
- Added optional Job ID to JobProfile.
- Updated the approved profile with details present in the supplied reference CV.

## Engineering
- Expanded requirements.txt to describe the actual runtime.
- Added deterministic Week 6 regression tests.
- Added Dockerfile and .dockerignore.
- Replaced placeholder README with architecture/build/test/release documentation.
