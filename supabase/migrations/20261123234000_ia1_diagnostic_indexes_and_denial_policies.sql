-- Cover diagnostic foreign keys and make direct-read denial explicit.
create index diagnostic_answers_question on public.diagnostic_answers(question_id);
create index diagnostic_answers_session_owner on public.diagnostic_answers(session_id,user_id);
create index diagnostic_sessions_question on public.diagnostic_sessions(current_question_id);
create index topic_progress_session_owner on public.topic_progress(session_id,user_id);
create policy diagnostic_questions_no_direct_read on public.diagnostic_questions for select to authenticated using (false);
create policy diagnostic_solutions_no_direct_read on public.diagnostic_solutions for select to authenticated using (false);
