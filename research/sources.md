# Sources

Everything this project claims about micro1's system comes from the two public sources below.
The paper PDF is deliberately **not** committed: it is freely available from arXiv, and
redistributing a third party's PDF is an avoidable licensing question. The quotations used
elsewhere in this repository are reproduced here so a reviewer can check them without leaving the
repo, and verify them against the original.

---

## 1. The Zara paper

> Yazdani, N., Mahajan, A., & Ansari, A. (2025). *Zara: An LLM-based Candidate Interview Feedback
> System.* arXiv:2507.02869 [cs.HC].
> <https://arxiv.org/abs/2507.02869>

### Quotations this project relies on

**On the architecture** (§3.1, Design Overview):

> "Zara leverages existing advanced LLM technologies, notably GPT-4o, rather than introducing novel
> algorithms."

**On what the paper does and does not open-source** (§3.1):

> "In this section, we briefly touch on phase (1) and (2) but focus specifically on phases (3) and
> (4), as these form the core of Zara's candidate support capabilities."

Phases (1) and (2) are interview preparation and the AI-led interview itself. Phases (3) and (4)
are post-interview feedback and candidate query resolution. **The interview-conduct policy is
therefore not published**, which is why this project makes no claim about how Zara is implemented
and why `baseline/prompt.md` is labelled as the obvious implementation rather than a reconstruction.

**On how the interview behaves** (§3.1, AI-led Interview) — the description `baseline/prompt.md`
is written from:

> "Zara serves as an autonomous interviewer engaging candidates in structured yet natural
> conversations, evaluating their technical competencies and conversational abilities. The model
> dynamically adjusts questions based on candidates' responses, providing an objective and scalable
> assessment while also answering any clarification questions the candidate has mid-interview."

**On the published metrics** (§5.1, Usage Metrics and Candidate Engagement):

| Metric | Human-led | Previous system | Zara |
|---|---:|---:|---:|
| Technical question quality | 7.78 | 8.38 | 8.60 |
| Conversational dynamics | 5.49 | 7.77 | 8.27 |

> "Candidate satisfaction with the AI-led interview experience was measured through Net Promoter
> Score (NPS). Based on 400 candidate ratings, Zara-enabled AI interviews received an average NPS
> rating of 4.37 out of 5."

Both quality metrics are **per-turn** properties. Neither is a session-level coverage measure, which
is the gap this project addresses.

**On scale** (§5.1):

> "There were 4820 'unsuccessful' interviews conducted, of which 10.7% requested detailed feedback."

Measured over a three-day window — roughly 1,600 screening interviews per day, of which 89.3% of
the unsuccessful candidates never requested the feedback that would tell them why.

**On the feedback output contract** (§4.1) — the shape `InterviewReport` stays compatible with:

> "Structure your feedback in JSON format with two main keys: 'strengths' and 'areas for
> improvement,' each containing 2-4 items. Each item includes: a 'title' key summarizing the
> feedback point. A 'detail' key offering constructive advice."

The same prompt instructs the model to "refrain from giving any feedback on soft skills and
communication" — the reason this project produces no behavioural score either.

---

## 2. The evaluation role

> micro1 public job board, *Full Stack Developer*, posted 2026-08-14, retrieved 2026-08-29.
> <https://jobs.micro1.ai/post/e4af7669-a52f-4f24-95f4-621259887aef>

Reproduced in `roles/fullstack/role.txt` with its source header. It is a genuine open micro1
position (50 openings at the time of retrieval), which means candidates applying to it are screened
by the system this project examines.

---

## 3. Interview methodology

The operational rules in `research/interview-guidance.md` are grounded in the structured-interview
literature. That file carries its own caveat: several figures come from indexed excerpts rather
than full readings. **Any figure quoted in the README must be re-verified against the primary
source first** (CLAUDE.md ground rule 9). The sources it cites:

- U.S. Office of Personnel Management (2008). *Structured Interviews: A Practical Guide.*
- Campion, M., Palmer, D., & Campion, J. (1997). A review of structure in the selection interview.
  *Personnel Psychology*, 50(3).
- Sackett, P. et al. (2022). Revisiting meta-analytic estimates of validity in personnel selection.
  *Journal of Applied Psychology.*
- Levashina, J. et al. (2014). The structured employment interview: narrative and quantitative
  review. *Personnel Psychology*, 67(1).
- Behroozi, M. et al. (2020). Does stress impact technical interview performance? *ESEC/FSE 2020.*
- Kong, H. et al. (2024). Gender bias in LLM-generated interview responses. arXiv:2410.20739.
  (Cited by the Zara paper itself.)
