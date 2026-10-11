document.querySelectorAll(".flash-close").forEach((button) => {
  button.addEventListener("click", () => button.closest(".flash")?.remove());
});

document.querySelectorAll("[data-copy-reference]").forEach((button) => {
  button.addEventListener("click", async () => {
    const reference = button.dataset.copyReference;
    if (!reference) return;

    try {
      await navigator.clipboard.writeText(reference);
      button.textContent = "Copied!";
    } catch {
      button.textContent = reference;
      window.setTimeout(() => {
        button.textContent = "Copy";
      }, 2500);
    }
  });
});

document.querySelectorAll('input[name="booking_ref"]').forEach((input) => {
  input.addEventListener("input", () => {
    input.value = input.value.toUpperCase().replace(/[^A-Z0-9]/g, "");
  });
});

document.querySelectorAll('select[name="boarding"]').forEach((origin) => {
  const form = origin.form;
  const destination = form?.querySelector('select[name="destination"]');
  if (!destination) return;

  form.addEventListener("submit", (event) => {
    if (origin.value === destination.value) {
      event.preventDefault();
      destination.setCustomValidity("Choose a destination different from your origin.");
      destination.reportValidity();
    } else {
      destination.setCustomValidity("");
    }
  });

  destination.addEventListener("change", () => destination.setCustomValidity(""));
});
