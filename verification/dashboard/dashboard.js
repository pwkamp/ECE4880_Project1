const badge = (name, value) => `<div class="card ${name}"><span>${name}</span><strong>${value ?? 0}</strong></div>`;
const outcomeLabel = (value) => value === 'PASS_OVERRIDE' ? 'PASS (OVERRIDE)' : value;
const status = (value) => `<span class="${cell(value)}">${cell(outcomeLabel(value))}</span>`;
const cell = (value = '') => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const list = values => values?.length ? `<ol>${values.map(value => `<li>${cell(value)}</li>`).join('')}</ol>` : '<p>None.</p>';

function procedure(definition, setupGroups) {
  const setup = setupGroups?.[definition.setup_group ?? 'software'] ?? {};
  const manualSteps = (definition.manual_steps ?? []).map(step => step.instruction ?? step.prompt ?? JSON.stringify(step));
  const command = definition.entrypoint?.command?.join(' ');
  const execution = command
    ? `<p><strong>Automated command</strong></p><pre>${cell(command)}</pre>`
    : definition.assisted_workflow
      ? `<p><strong>Guided workflow</strong>: ${cell(definition.assisted_workflow)}</p>`
      : '<p>This procedure is recorded directly by the operator.</p>';
  return `<div class="procedure-grid">
    <article class="editor-card"><h4>What this test verifies</h4><p>${cell(definition.description ?? 'No description recorded.')}</p><p><strong>Why it is valid:</strong> ${cell(definition.rationale ?? 'No rationale recorded.')}</p></article>
    <article class="editor-card"><h4>Required setup</h4><p><strong>${cell(setup.title ?? definition.setup_group ?? 'Software')}</strong></p>${list(setup.instructions ?? [])}</article>
    <article class="editor-card"><h4>Execution procedure</h4>${execution}${manualSteps.length ? list(manualSteps) : ''}</article>
    <article class="editor-card"><h4>Pass policy</h4><pre>${cell(JSON.stringify(definition.pass_policy ?? {}, null, 2))}</pre><p><strong>Limitations:</strong> ${cell((definition.limitations ?? []).join('; ') || 'None')}</p></article>
  </div>`;
}

async function load() {
  const response = await fetch('latest.json', { cache: 'no-store' });
  if (!response.ok) throw new Error('Run a verification profile to create dashboard data.');
  const data = await response.json();
  const run = data.run;
  const resume = run.resumed_from_run
    ? ` | resumed from ${run.resumed_from_run}: ${(run.reused_test_ids ?? []).length} imported, ${(run.executed_test_ids ?? []).length} rerun`
    : '';
  document.querySelector('#run-meta').textContent = `${run.run_id} | ${run.profile} | ${run.started_at_utc} | ${run.duration_ms ?? '?'} ms | ${run.git_sha ?? 'unknown git'} | ${run.git_state}${resume}`;
  const outcomes = ['PASS', 'PASS_OVERRIDE', 'FAIL', 'BLOCKED', 'SKIPPED', 'NOT_APPLICABLE'];
  document.querySelector('#summary').innerHTML = outcomes.map(name => badge(name, data.results.filter(item => item.outcome === name).length)).join('');
  document.querySelector('#coverage').innerHTML = outcomes.map(name => badge(name, data.coverage.counts[name])).join('');
  const unmapped = data.coverage.counts.UNMAPPED ?? 0;
  const unmappedNode = document.querySelector('#unmapped');
  unmappedNode.textContent = `Unmapped active requirements: ${unmapped}`;
  unmappedNode.className = unmapped ? 'bad' : 'PASS';
  const manualResults = data.results.filter(item => item.method !== 'automated');
  const manualBlocked = manualResults.filter(item => item.outcome === 'BLOCKED').length;
  document.querySelector('#manual-notice').textContent = `${manualResults.length} tests require human participation; ${manualBlocked} are currently BLOCKED. Open any row to edit its saved result. PASS (OVERRIDE) is retained as a visibly overridden pass and requires an evidence-based comment.`;

  document.querySelector('#fixtures').innerHTML = Object.values(data.fixtures).map(item => `<tr><td>${cell(item.name)}</td><td>${status(item.status)}</td><td>${cell(item.detail)}</td></tr>`).join('');
  document.querySelector('#instrumentation').innerHTML = Object.values(data.instrumentation).map(item => `<tr><td>${cell(item.name)}</td><td>${status(item.status)}</td><td>${cell(item.detail)}</td></tr>`).join('');
  document.querySelector('#setup-sections').innerHTML = (data.setup_transitions ?? []).map(item => {
    const configured = data.setup_groups?.[item.setup_group] ?? {};
    const instructions = (item.instructions ?? configured.instructions ?? []).map(value => `<li>${cell(value)}</li>`).join('');
    return `<article class="setup-card ${item.confirmed ? 'setup-confirmed' : 'setup-blocked'}"><h3>${cell(item.title ?? item.setup_group)}</h3><p>${status(item.confirmed ? 'CONFIRMED' : 'BLOCKED')} | Tests: ${cell((item.tests ?? []).join(', '))}${item.uart_port ? ` | UART: ${cell(item.uart_port)}` : ''}</p><ol>${instructions}</ol></article>`;
  }).join('') || '<p>No setup transitions were recorded for this legacy run.</p>';
  document.querySelector('#tests').innerHTML = data.results.map(item => {
    const notes = item.human_intervention || (item.limitations ?? []).join('; ') || 'None';
    const evidence = (item.evidence ?? []).map(path => `<a href="/artifacts/verification/${cell(run.run_id)}/${cell(path)}">view</a>`).join(' ');
    const classes = [item.method === 'automated' ? '' : 'manual-row', item.reused ? 'reused-row' : ''].filter(Boolean).join(' ');
    const source = item.reused ? `<span class="source-tag">imported from ${cell(item.reused_from_run)}</span>` : '<span class="source-tag executed">executed in this run</span>';
    return `<tr${classes ? ` class="${classes}"` : ''}><td><button class="test-select" data-test-id="${cell(item.test_id)}">${cell(item.test_id)} - ${cell(item.title)}</button><br>${source}</td><td>${cell(item.setup_group ?? 'software')}</td><td>${cell(item.subsystem)}</td><td>${cell(item.method)}</td><td>${status(item.outcome)}</td><td>${cell(notes)}</td><td>${evidence || '-'}</td></tr>`;
  }).join('');

  document.querySelectorAll('.test-select').forEach(button => button.addEventListener('click', () => {
    const id = button.dataset.testId;
    const result = data.results.find(item => item.test_id === id);
    const definition = data.test_catalog.find(item => item.id === id) ?? {};
    const history = data.history[id] ?? [];
    const historyRows = history.map(item => {
      const links = (item.evidence ?? []).map(path => `<a href="/artifacts/verification/${cell(item.run_id)}/${cell(path)}">evidence</a>`).join(' ');
      return `<tr><td>${cell(item.run_id)}</td><td>${cell(item.profile)}</td><td>${status(item.outcome)}</td><td>${cell(item.duration_ms)} ms</td><td>${links || '-'}</td></tr>`;
    }).join('');
    const detail = document.querySelector('#test-detail');
    detail.hidden = false;
    const decisionOptions = outcomes.map(value => `<option value="${value}" ${result.outcome === value ? 'selected' : ''}>${outcomeLabel(value)}</option>`).join('');
    const currentEvidence = (result.evidence ?? []).map(path => `<li><a href="/artifacts/verification/${cell(run.run_id)}/${cell(path)}">${cell(path)}</a></li>`).join('') || '<li>No evidence files recorded.</li>';
    const decision = `<article class="result-editor"><h4>Result editor</h4>
      <p>Choose the result supported by the procedure and retained evidence. <strong>PASS (OVERRIDE)</strong> is for an original automated/manual failure that the evidence proves was actually a pass; explain that discrepancy in the required comment.</p>
      <form class="adjudication" id="adjudication-form">
        <label for="operator">Operator</label><input id="operator" required value="${cell(result.adjudication?.operator ?? '')}">
        <label for="decision">Decision</label><select id="decision">${decisionOptions}</select>
        <label for="reason">Required evidence-based comment</label><textarea id="reason" required rows="4">${cell(result.adjudication?.reason ?? '')}</textarea>
        <button type="submit">Record decision</button><div class="adjudication-message" id="adjudication-message"></div>
      </form></article>`;
    detail.innerHTML = `<div class="editor-heading"><div><span class="editor-kicker">Test result editor</span><h3>${cell(id)} - ${cell(result.title)}</h3></div><div>${status(result.outcome)}</div></div>
      ${procedure(definition, data.setup_groups)}
      <p><strong>Requirements:</strong> ${cell((result.requirements ?? []).join(', '))}</p>
      <p><strong>Fixtures:</strong> ${cell(JSON.stringify(result.fixtures))}</p>
      <p><strong>Instrumentation:</strong> ${cell(JSON.stringify(result.instrumentation))}</p>
      <div class="result-grid"><article class="editor-card"><h4>Captured measurements</h4><pre>${cell(JSON.stringify(result.metrics ?? {}, null, 2))}</pre></article><article class="editor-card"><h4>Evidence files</h4><ul>${currentEvidence}</ul></article></div>
      <div class="result-context"><p><strong>Original outcome:</strong> ${status(result.original_outcome ?? result.outcome)}</p>
      <p><strong>Execution source:</strong> ${result.reused ? `Imported from ${cell(result.reused_from_run)}; original execution ${cell(result.source_started_at_utc ?? 'unknown')}` : 'Executed in this run'}</p>
      <p><strong>Failure/block reason:</strong> ${cell(result.failure_reason ?? 'None')}</p></div>
      ${decision}
      <h4>Historical runs</h4><div class="table-wrap"><table><thead><tr><th>Run</th><th>Profile</th><th>Outcome</th><th>Duration</th><th>Evidence</th></tr></thead><tbody>${historyRows}</tbody></table></div>`;
    const form = document.querySelector('#adjudication-form');
    form?.addEventListener('submit', async event => {
      event.preventDefault();
      const response = await fetch('/api/adjudicate', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ run_id: run.run_id, test_id: id, outcome: document.querySelector('#decision').value, operator: document.querySelector('#operator').value, reason: document.querySelector('#reason').value }),
      });
      const answer = await response.json();
      document.querySelector('#adjudication-message').textContent = answer.message;
      if (response.ok) setTimeout(() => location.reload(), 500);
    });
    detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }));

  document.querySelector('#requirements').innerHTML = data.coverage.requirements.map(item => `<tr><td>${cell(item.uid)}</td><td><a href="https://pkamp.atlassian.net/browse/${cell(item.jira)}">${cell(item.jira)}</a></td><td>${status(item.result)}</td><td>${cell(item.tests.join(', '))}</td><td>${cell(item.human_tests.join(', ') || 'None')}</td><td>${cell(item.reason)}</td></tr>`).join('');
}

load().catch(error => { document.querySelector('#run-meta').textContent = error.message; });
