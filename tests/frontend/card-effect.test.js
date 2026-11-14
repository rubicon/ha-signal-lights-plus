/**
 * Per-signal effect and brightness in the card: shown on each row and
 * editable in the add and edit forms.
 */
import { describe, it, expect, afterEach } from 'vitest';
import {
  FakeHass,
  makeSnapshot,
  makeSignal,
  mountCard,
  flush,
} from './helpers/fake-hass.js';

afterEach(() => {
  document.body.innerHTML = '';
});

async function openEditForm(signal) {
  const hass = new FakeHass(makeSnapshot({ signals: [signal] }));
  const card = await mountCard(hass);
  card.shadowRoot.querySelector('.btn-edit').click();
  await flush();
  return { hass, card, form: card.shadowRoot.querySelector('.edit-signal-form-container') };
}

describe('signal row', () => {
  it('shows the effect and brightness when they are set', async () => {
    const hass = new FakeHass(makeSnapshot({
      signals: [makeSignal({ effect: 'pulse', brightness: 80 })],
    }));
    const card = await mountCard(hass);
    const fx = card.shadowRoot.querySelector('.signal-row .signal-fx');
    expect(fx).toBeTruthy();
    expect(fx.textContent).toContain('Effect: pulse');
    expect(fx.textContent).toContain('Brightness: 80');
  });

  it('shows only the setting that is set', async () => {
    const hass = new FakeHass(makeSnapshot({
      signals: [makeSignal({ brightness: 80 })],
    }));
    const card = await mountCard(hass);
    const fx = card.shadowRoot.querySelector('.signal-row .signal-fx');
    expect(fx.textContent).toContain('Brightness: 80');
    expect(fx.textContent).not.toContain('Effect');
  });

  it('shows nothing extra for a signal with neither', async () => {
    const hass = new FakeHass(makeSnapshot());
    const card = await mountCard(hass);
    expect(card.shadowRoot.querySelector('.signal-fx')).toBeNull();
  });

  it('escapes the effect name', async () => {
    const hass = new FakeHass(makeSnapshot({
      signals: [makeSignal({ effect: '<img src=x onerror=alert(1)>' })],
    }));
    const card = await mountCard(hass);
    const row = card.shadowRoot.querySelector('.signal-row');
    expect(row.querySelector('img')).toBeNull();
    expect(row.querySelector('.signal-fx').textContent).toContain('<img src=x onerror=alert(1)>');
  });
});

describe('edit form', () => {
  it('pre-populates effect and brightness', async () => {
    const { form } = await openEditForm(makeSignal({ effect: 'blink', brightness: 120 }));
    expect(form.querySelector('#sl-edit-sig-effect').value).toBe('blink');
    expect(form.querySelector('#sl-edit-sig-brightness').value).toBe('120');
  });

  it('leaves both fields empty for a signal with neither', async () => {
    const { form } = await openEditForm(makeSignal());
    expect(form.querySelector('#sl-edit-sig-effect').value).toBe('');
    expect(form.querySelector('#sl-edit-sig-brightness').value).toBe('');
  });

  it('save sends the edited effect and brightness', async () => {
    const { hass, form } = await openEditForm(makeSignal());
    form.querySelector('#sl-edit-sig-effect').value = '  pulse ';
    form.querySelector('#sl-edit-sig-brightness').value = '40';
    form.querySelector('#sl-edit-sig-save').click();
    await flush();
    const call = hass.serviceCalls.find((c) => c.service === 'update_signal');
    expect(call.data.effect).toBe('pulse');
    expect(call.data.brightness).toBe(40);
  });

  it('save with both fields emptied clears them', async () => {
    const { hass, form } = await openEditForm(makeSignal({ effect: 'blink', brightness: 120 }));
    form.querySelector('#sl-edit-sig-effect').value = '';
    form.querySelector('#sl-edit-sig-brightness').value = '';
    form.querySelector('#sl-edit-sig-save').click();
    await flush();
    const call = hass.serviceCalls.find((c) => c.service === 'update_signal');
    expect(call.data.effect).toBe('');
    expect(call.data.brightness).toBeNull();
  });

  it('keeps the typed effect when the trigger mode changes', async () => {
    const { card, form } = await openEditForm(makeSignal());
    form.querySelector('#sl-edit-sig-effect').value = 'pulse';
    form.querySelector('#sl-edit-sig-brightness').value = '33';
    const modeSelect = form.querySelector('#sl-edit-sig-trigger-mode');
    modeSelect.value = 'template';
    modeSelect.dispatchEvent(new Event('change'));
    await flush();
    const after = card.shadowRoot.querySelector('.edit-signal-form-container');
    expect(after.querySelector('#sl-edit-sig-effect').value).toBe('pulse');
    expect(after.querySelector('#sl-edit-sig-brightness').value).toBe('33');
  });
});

describe('add form', () => {
  async function fillAndSubmit(extra) {
    const hass = new FakeHass(makeSnapshot({ signals: [] }));
    const card = await mountCard(hass);
    card.shadowRoot.getElementById('sl-add-signal-btn').click();
    await flush();
    const form = card.shadowRoot.getElementById('sl-add-signal-form');
    form.querySelector('#sl-sig-name').value = 'Garage open';
    form.querySelector('#sl-sig-entity').value = 'binary_sensor.garage';
    form.querySelector('#sl-sig-state').value = 'on';
    extra(form);
    form.querySelector('#sl-add-signal-submit').click();
    await flush();
    return hass.serviceCalls.find((c) => c.service === 'add_signal');
  }

  it('sends the effect and brightness when given', async () => {
    const call = await fillAndSubmit((form) => {
      form.querySelector('#sl-sig-effect').value = 'blink';
      form.querySelector('#sl-sig-brightness').value = '90';
    });
    expect(call.data.effect).toBe('blink');
    expect(call.data.brightness).toBe(90);
  });

  it('leaves both out when empty', async () => {
    const call = await fillAndSubmit(() => {});
    expect('effect' in call.data).toBe(false);
    expect('brightness' in call.data).toBe(false);
  });
});
