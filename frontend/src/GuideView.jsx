import React from "react";

export function GuideView({ onSetup }) {
  return (
    <div className="workflow-page guide">
      <h1>Read a report in four steps</h1>
      <p className="lead">
        Start with the result. Use the details when you need them.
      </p>
      <section className="panel">
        <h2>1. Check the scope</h2>
        <p>
          Confirm the device, test profile and case count. One report covers one
          visible device or partition. A passed case does not certify every
          hardware unit.
        </p>
      </section>
      <section className="panel">
        <h2>2. Understand the result</h2>
        <dl className="guide-states">
          <dt className="positive">Passed</dt>
          <dd>
            The result matches the reference within the allowed tolerance.
          </dd>
          <dt className="negative">Mismatch</dt>
          <dd>
            A value, shape or index is unexpected. Save the evidence and retest.
          </dd>
          <dt className="caution">Inconclusive</dt>
          <dd>The runtime, budget or available evidence was insufficient.</dd>
          <dt>Not run</dt>
          <dd>
            The case has no result. Tests may stop after the first mismatch.
          </dd>
        </dl>
      </section>
      <section className="panel">
        <h2>3. Separate a mismatch from its cause</h2>
        <p>
          Silent data corruption (SDC) means an incorrect result without an
          obvious error signal. A mismatch is a clue: hardware, drivers,
          compilers and test code can all cause it.
        </p>
        <p>
          Low-precision rounding can be expected. Equal topk values may also
          have different valid indices. Omnismi checks these rules before
          reporting a mismatch.
        </p>
      </section>
      <section className="panel">
        <h2>4. Keep evidence and compare</h2>
        <ol>
          <li>Save the JSON report and any NPZ evidence files.</li>
          <li>Repeat with the same settings on the same device.</li>
          <li>Compare another device or runtime version.</li>
          <li>Combine the results with vendor diagnostics and error logs.</li>
        </ol>
        <button className="button primary" onClick={onSetup}>
          Prepare a test
        </button>
      </section>
      <p className="muted">
        Files stay local. Refreshing clears manually imported reports. Use
        dashboard --report to preload a file. This viewer does not run tests or
        collect live metrics.
      </p>
    </div>
  );
}
