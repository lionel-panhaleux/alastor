function hide() {
    this.style.display = "none"
}
function display_login_modal() {
    document.getElementById("login-submit").formAction = `/api/login?next=${encodeURIComponent(
        window.location.pathname
    )}`
    document.getElementById("signup-submit").formAction = `/api/signup?next=${encodeURIComponent(
        window.location.pathname
    )}`
    console.log(document.getElementById("signup-submit").action)
    document.getElementById("login-modal-content").addEventListener("click", (e) => e.stopPropagation())
    document.getElementById("login-modal").addEventListener("click", hide)
    document.getElementById("login-modal").style.display = "block"
}
function logout() {
    let form = document.getElementById("logout-form")
    form.action = `/api/logout?next=${encodeURIComponent(window.location.pathname)}`
    form.submit()
}
function load_current_page() {
    for (let elem of document.getElementById("navigation").children) {
        if (elem.tagName === "A") {
            if (elem.href === window.location.href) {
                elem.classList.add("current-page")
            } else {
                elem.classList.remove("current-page")
            }
        }
    }
}
function load() {
    load_current_page()
}
window.addEventListener("load", load)
