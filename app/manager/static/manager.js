(() => {
  const toast = (message, kind = "") => {
    const node = document.querySelector("#toast");
    if (!node) return;
    node.textContent = message;
    node.className = `toast visible ${kind}`;
    window.setTimeout(() => node.classList.remove("visible"), 4200);
  };
  const csrf = () => document.cookie.split("csrf_token=")[1]?.split(";")[0] || "";
  const post = async (url, payload = {}) => {
    const response = await fetch(url, {
      method: "POST",
      headers: { "X-CSRF-Token": csrf(), "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Không thực hiện được thao tác.");
    return data;
  };
  window.managerPost = post;
  window.managerToast = toast;
  document.querySelectorAll("[data-scan-all]").forEach((scanButton) => scanButton.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    button.classList.add("is-loading");
    try {
      const result = await post("/scan");
      toast(`Đã quét xong: ${result.folders_seen ?? 0} thư mục, ${result.files_seen ?? 0} PDF.` , "success");
      window.setTimeout(() => window.location.reload(), 650);
    } catch (error) {
      toast(error.message, "error");
      button.disabled = false;
      button.classList.remove("is-loading");
    }
  }));
  document.querySelectorAll("[data-confirm-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const message = button.dataset.confirmAction || "Xác nhận thao tác này?";
      if (!window.confirm(message)) return;
      button.disabled = true;
      try {
        await post(button.dataset.url, button.dataset.payload ? JSON.parse(button.dataset.payload) : {});
        toast("Đã cập nhật.", "success");
        window.setTimeout(() => window.location.reload(), 350);
      } catch (error) {
        toast(error.message, "error");
        button.disabled = false;
      }
    });
  });
})();
