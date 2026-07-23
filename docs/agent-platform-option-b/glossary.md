# Glossary

- **Workflow definition:** A versioned specification of a business process, its objective, steps,
  inputs, outputs, policies, and deployment mode.
- **Workflow run:** One durable execution of a workflow caused by an event or person.
- **Workflow step:** One recorded unit of deterministic logic, AI judgment, validation, approval,
  waiting, tool execution, or outcome capture.
- **AI execution:** A first-class record of one model call, including structured input/output,
  model and prompt versions, context references, cost, latency, and parse status.
- **Tool call:** A permission-checked request to a typed business capability, with idempotency,
  attempts, and a sanitized result.
- **Approval request:** A reviewable proposed action with its reason, evidence, risk, expiry,
  authority requirement, decision, edits, and result.
- **Human correction:** A preserved difference between an AI proposal and the reviewed result,
  including a structured reason.
- **Outcome:** An observed business or operational result linked to a workflow run.
- **Evaluation dataset:** A versioned set of reviewed examples and expected behavior.
- **Evaluation run:** A regression assessment of a workflow/model/prompt/policy version against a
  dataset.
- **Shadow mode:** Real inputs are processed and traced, but no external action is executed.
- **Approval-required mode:** An external action is proposed but cannot run until authorized.
- **Limited autonomy:** Only explicitly permitted, evaluated, reversible low-risk actions can run
  without per-action approval.
- **Idempotency:** Repeating the same request cannot perform the external effect more than once.
- **Durable execution:** Workflow state survives request failures, worker restarts, and retries.
- **Tenant isolation:** One business cannot read, associate, influence, or act on another
  business's data or credentials.
- **Business context:** Tenant facts, policies, records, state, and history supplied for a task.
- **Authoritative source:** A reviewed system of record, such as the approved price catalogue,
  rather than an inference or customer statement.
- **Memory:** Stored information intentionally available to later tasks; conversation history
  alone is not automatically authoritative memory.
- **Feedback:** A human or outcome signal about a system result.
- **Learning:** A controlled, evaluated change to future behavior. Storing feedback or chat history
  is not learning by itself.

