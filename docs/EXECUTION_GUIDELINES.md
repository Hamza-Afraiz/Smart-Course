# SmartCourse — Execution Guidelines

## 1. Objective

This assignment is a structured learning journey. The goal is not just to deliver features, but to:

- Build a strong understanding of distributed systems and scalable architecture
- Gain hands-on experience with event-driven design and workflows
- Learn how to design for reliability, consistency, and observability
- Develop confidence working with the defined tech stack
- Apply design principles and real-world engineering practices

---

## 2. Execution Approach

### Module-Based Progression
- Structured in weekly modules
- Complete each module within the assigned week
- Share progress with mentor for review
- Address feedback before moving ahead

### Weekly Milestone Flow
1. Work on the assigned milestone
2. Submit for mentor review
3. Discuss feedback and suggestions
4. Refine implementation
5. Move to next module

### Mentor Collaboration
During reviews:
- Walk through approach and decisions
- Highlight challenges faced
- Ask questions where things were unclear

Reviews focus on: design clarity, system thinking, understanding of tools and patterns.

---

## 3. Submission Guidelines

### GitHub Repository
- Organized project structure
- Clear module/service separation
- Meaningful commits

### README
- Project overview
- Architecture diagram
- Setup instructions
- API overview
- Tech stack used

### Technical Documentation
- Service/module breakdown
- Data flow and event flow
- Key design decisions
- Assumptions and tradeoffs

---

## 4. Learning Expectations

### Part A (Core Platform)
- Event-driven architecture
- Idempotency and consistency
- Distributed workflows (Temporal)
- Async processing (Kafka, Celery)

### Part B (GenAI Layer)
- Embeddings and vector search
- Retrieval-Augmented Generation (RAG)
- Prompt design and response quality
- Streaming responses and latency

---

## 5. Part A — Execution Plan (3 Weeks)

### 🟢 Week 1 — Foundation + Core Services

**Scope**
- Initial system design and setup
- User & Course management (basic CRUD)
- Role handling (student/instructor)

**Deliverables**
- [ ] Service structure defined
- [ ] Database schema created
- [ ] Basic APIs working
- [ ] Local setup ready

---

### 🟡 Week 2 — Enrollment + Publishing Workflow

**Scope**
- Enrollment system (duplicate handling, basic validations)
- Course publishing workflow using Temporal
- Content structure (modules/lessons)

**Deliverables**
- [ ] Enrollment flow working reliably
- [ ] Workflow orchestration integrated
- [ ] Course state transitions handled

---

### 🔴 Week 3 — Event-Driven System + Observability

**Scope**
- Kafka integration for events
- Background workers (Celery)
- Basic analytics metrics
- Observability setup (logs, tracing, metrics)

**Deliverables**
- [ ] Event-driven flows working
- [ ] Analytics pipeline initialized
- [ ] Basic monitoring and tracing available

---

### Part A — Weekly Tracking Table

| Week | Focus Area | What to Aim For | Done |
|------|-----------|----------------|------|
| Week 1 | Foundation & Core Services | Working APIs, DB design, system structure | ⬜ |
| Week 2 | Enrollment & Workflows | Stable enrollment + publishing workflow | ⬜ |
| Week 3 | Events & Observability | Async processing + visibility into system | ⬜ |

---

## 6. Part B — Execution Plan (2 Weeks)

### 🟣 Week 4 — Data Preparation + Retrieval

**Scope**
- Content chunking (from Part A)
- Embedding generation
- Vector database integration
- Retrieval pipeline

**Deliverables**
- [ ] Content indexed for semantic search
- [ ] Relevant data retrieval working

---

### 🔵 Week 5 — AI Assistant + Streaming

**Scope**
- Contextual Q&A system
- Instructor content generation (summaries, quizzes)
- Streaming or non-blocking responses

**Deliverables**
- [ ] Functional AI assistant
- [ ] Context-aware responses
- [ ] Smooth user interaction flow

---

### Part B — Weekly Tracking Table

| Week | Focus Area | What to Aim For | Done |
|------|-----------|----------------|------|
| Week 4 | Retrieval Layer | Indexed content + working semantic search | ⬜ |
| Week 5 | AI Assistant | End-to-end Q&A + content generation | ⬜ |

---

## 7. Final Deliverables Checklist

- [ ] All modules completed and reviewed
- [ ] Codebase clean and well-structured
- [ ] README and documentation complete
- [ ] Key workflows working end-to-end
- [ ] Comfortable explaining your design

---

## 8. Evaluation Approach

Evaluation is based on:
- Clarity of architecture
- Code quality and structure
- Use of the tech stack
- Handling of edge cases and failures
- Observability and system thinking
- Depth of understanding
