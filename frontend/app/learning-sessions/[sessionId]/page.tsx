import { apiFetch, demoToken } from "../../../lib/api";

type Checkpoint = {
  id: string;
  title: string;
  objective: string;
  study_material: string;
  quiz_questions: string[];
  score: number | null;
  passed: boolean | null;
  feedback: string | null;
  simplified_material: string | null;
  order_index: number;
};

type LearningSession = {
  id: string;
  status: string;
  current_checkpoint_index: number;
  preferred_explanation_style: string | null;
  comments: {
    id: string;
    body: string;
    anchor: string | null;
  }[];
  checkpoints: Checkpoint[];
};

async function getLearningSession(sessionId: string): Promise<LearningSession | null> {
  if (!demoToken) {
    return null;
  }
  try {
    return await apiFetch<LearningSession>(`/learning-sessions/${sessionId}`, {
      token: demoToken,
    });
  } catch {
    return null;
  }
}

export default async function LearningSessionPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  const session = await getLearningSession(sessionId);

  if (!session) {
    return (
      <div className="panel empty">
        Learning session data is unavailable. Start a session from a report and set
        the demo token to inspect it here.
      </div>
    );
  }

  return (
    <div className="panel stack">
      <div className="eyebrow">Learning session</div>
      <h2>Checkpoint progression</h2>
      <div className="chip-row">
        <span className="chip">Status: {session.status}</span>
        <span className="chip">Current checkpoint: {session.current_checkpoint_index}</span>
        {session.preferred_explanation_style ? (
          <span className="chip">Style: {session.preferred_explanation_style}</span>
        ) : null}
      </div>

      <div className="card-list">
        {session.checkpoints.map((checkpoint) => (
          <div className="card" key={checkpoint.id}>
            <h3>
              {checkpoint.order_index + 1}. {checkpoint.title}
            </h3>
            <p className="muted">{checkpoint.objective}</p>
            <p>{checkpoint.study_material}</p>
            <ul className="list muted">
              {checkpoint.quiz_questions.map((question) => (
                <li key={question}>{question}</li>
              ))}
            </ul>
            <div className="meta">
              <span>Score: {checkpoint.score ?? "Not graded yet"}</span>
              <span>Passed: {checkpoint.passed === null ? "Pending" : String(checkpoint.passed)}</span>
            </div>
            {checkpoint.feedback ? (
              <div className="card" style={{ marginTop: 14 }}>
                <strong>Feedback</strong>
                <p className="muted">{checkpoint.feedback}</p>
                {checkpoint.simplified_material ? (
                  <>
                    <strong>Simplified explanation</strong>
                    <p className="muted">{checkpoint.simplified_material}</p>
                  </>
                ) : null}
              </div>
            ) : null}
          </div>
        ))}
      </div>

      <div className="eyebrow" style={{ marginTop: 24 }}>Session comments</div>
      <div className="card-list">
        {session.comments.length === 0 ? (
          <div className="empty">
            No collaboration comments yet. Use the learning-session comment
            endpoint to capture mentor notes or peer feedback.
          </div>
        ) : (
          session.comments.map((comment) => (
            <div className="card" key={comment.id}>
              <p>{comment.body}</p>
              {comment.anchor ? <div className="meta"><span>{comment.anchor}</span></div> : null}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
