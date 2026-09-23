const badge = (name, value) => `<div class="card ${name}"><span>${name}</span><strong>${value ?? 0}</strong></div>`;
const status = (value) => `<span class="${value}">${value}</span>`;
const cell = (value = '') => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');

async function load() {
  const response = await fetch('latest.json', { cache: 'no-store' });
  if (!response.ok) throw new Error('Run a verification profile to create dashboard data.');
  const data = await response.json();
  const run = data.run;
  document.querySelector('#run-meta').textContent = `${run.run_id} | ${run.profile} | ${run.started_at_utc} | ${run.duration_ms ?? '?'} ms | ${run.git_sha ?? 'unknown git'} | ${run.git_state}`;
  const outcomes = ['PASS', 'FAIL', 'BLOCKED', 'SKIPPED', 'NOT_APPLICABLE'];
  document.querySelector('#summary').innerHTML = outcomes.map(name => badge(name, data.results.filter(item => item.outcome === name).length)).join('');
  document.querySelector('#coverage').innerHTML = outcomes.map(name => badge(name, data.coverage.counts[name])).join('');
  const unmapped = data.coverage.counts.UNMAPPED ?? 0;
  const unmappedNode = document.querySelector('#unmapped');
  unmappedNode.textContent = `Unmapped active requirements: ${unmapped}`;
  unmappedNode.className = unmapped ? 'bad' : 'PASS';
  const manualResults = data.results.filter(item => item.method !== 'automated');
  const manualBlocked = manualResults.filter(item => item.outcome === 'BLOCKED').length;
  document.querySelector('#manual-notice').textContent = `${manualResults.length} tests require human participation; ${manualBlocked} are currently BLOCKED. Open a yellow row to record a per-run operator decision.`;

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
    const manualClass = item.method === 'automated' ? '' : ' class="manual-row"';
    return `<tr${manualClass}><td><button class="test-select" data-test-id="${cell(item.test_id)}">${cell(item.test_id)} - ${cell(item.title)}</button></td><td>${cell(item.setup_group ?? 'software')}</td><td>${cell(item.subsystem)}</td><td>${cell(item.method)}</td><td>${status(item.outcome)}</td><td>${cell(notes)}</td><td>${evidence || '-'}</td></tr>`;
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
    const decision = result.method === 'automated' ? '' : `<h4>Operator decision for this run</h4>
      <form class="adjudication" id="adjudication-form">
        <label for="operator">Operator</label><input id="operator" required value="${cell(result.adjudication?.operator ?? '')}">
        <label for="decision">Decision</label><select id="decision"><option>PASS</option><option>FAIL</option><option>BLOCKED</option></select>
        <label for="reason">Evidence-based rationale</label><input id="reason" required value="${cell(result.adjudication?.reason ?? '')}">
        <button type="submit">Record decision</button><div class="adjudication-message" id="adjudication-message"></div>
      </form>`;
    detail.innerHTML = `<h3>${cell(id)} - ${cell(result.title)}</h3>
      <p>${cell(definition.description ?? '')}</p>
      <p><strong>Test rationale:</strong> ${cell(definition.rationale ?? '')}</p>
      <p><strong>Requirements:</strong> ${cell((result.requirements ?? []).join(', '))}</p>
      <p><strong>Fixtures:</strong> ${cell(JSON.stringify(result.fixtures))}</p>
      <p><strong>Instrumentation:</strong> ${cell(JSON.stringify(result.instrumentation))}</p>
      <p><strong>Measurements:</strong></p><pre>${cell(JSON.stringify(result.metrics ?? {}, null, 2))}</pre>
      <p><strong>Failure/block reason:</strong> ${cell(result.failure_reason ?? 'None')}</p>
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
