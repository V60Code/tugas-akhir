---
trigger: always_on
---

# Coding Standards & Conventions

## 1. Python (Backend - FastAPI & Celery)

### Naming & Style
- Use **Snake Case** (`variable_name`, `function_name`) for variables, functions, and file names.
- Use **Pascal Case** (`ClassName`) for Classes, Pydantic Models, and Enum classes.
- Use **UPPER_CASE** for constants (e.g., `DEFAULT_MAX_TOKENS = 4000`).
- Follow **PEP 8** guidelines. Use `ruff` or `black` for auto-formatting.

### Async & Performance
- **Async by Default:** Use `async def` for all FastAPI route handlers and database queries.
- **Blocking Code:** Never perform blocking I/O (like `requests.get` or heavy CPU loops) inside an `async def` route. Use `run_in_executor` or offload to **Celery**.
- **Dependency Injection:** Always use FastAPI's `Depends()` for database sessions and services (e.g., `db: AsyncSession = Depends(get_db)`).

### Typing & Validation
- **Strict Typing:** All function arguments and return values MUST have Type Hints.
  - *Bad:* `def process(data):`
  - *Good:* `def process(data: dict[str, Any]) -> JobSchema:`
- **Pydantic:** Always return Pydantic schemas from API endpoints. Never return raw SQLAlchemy ORM objects directly to the client.

### Error Handling
- Do not return raw 500 errors. Use `HTTPException` with clear detail messages.
- Log errors before raising exceptions using the standard `logging` module or `structlog`.

---

## 2. TypeScript (Frontend - Next.js)

### Naming & Structure
- Use **Pascal Case** for Components and Pages (`JobCard.tsx`, `page.tsx`).
- Use **Camel Case** for variables, hooks, and functions (`isLoading`, `handleSubmit`).
- **Component Structure:** One component per file. If a component needs sub-components, place them in a folder with the same name or inside the file if they are tiny and private.

### React & Next.js Patterns
- **Functional Components:** Use Functional Components with Hooks (`const MyComp = () => {}`), NOT Class Components.
- **Server vs Client:** Explicitly add `"use client"` at the top of files that use Hooks (`useState`, `useEffect`, `zustand`). Default to Server Components otherwise.
- **Strict Props:** Use `interface` (not `type`) for defining component props. Prefix with component name (e.g., `JobCardProps`).

### State & Data
- **No `any`:** Avoid `any` at all costs. Use `unknown` or define a specific interface.
- **API Calls:** Place all API calls in `src/lib/api/` folder. Do not write `fetch/axios` directly inside UI components.
- **Zustand:** Keep stores atomic. Do not put complex business logic inside the store; keep it in `actions` or `services`.

### Styling (Tailwind)
- Use `clsx` or `cn` (shadcn utility) for conditional classes.
- Order classes logically (Layout -> Spacing -> Visuals) or rely on the prettier-plugin-tailwindcss.

---

## 3. AI & Prompt Engineering Standards
- **No Hardcoded Prompts:** Do not write long prompt strings inside function logic. Store them in `app/core/prompts/` or a dedicated constants file.
- **Output Parsing:** Always use LangChain's `PydanticOutputParser` to guarantee JSON output. Never rely on Regex to parse LLM responses.
- **Error Handling:** Wrap all LLM calls in try-except blocks to handle Timeouts or Rate Limits gracefully.

---

## 4. Git & File Structure
- **Monorepo Strictness:** Do not import backend code into frontend files or vice versa.
- **Atomic Commits:** Commit messages should follow Conventional Commits (e.g., `feat: add upload endpoint`, `fix: resolve parsing error`).