async function load_cities(e) {
    const select_country = document.getElementById("select-country")
    let select_city = document.getElementById("select-city")
    while (select_city.children.length > 1) {
        select_city.removeChild(select_city.lastChild)
    }
    if (select_country.value === "") {
        select_city.classList.add("hidden")
        return
    }
    select_city.classList.remove("hidden")
    try {
        const response = await fetch("/api/cities/" + select_country.value, {
            method: "GET",
            headers: { Accept: "application/json" },
        })
        if (!response.ok) {
            throw Error(response.statusText)
        }
        const data = await response.json()
        for (const city of data) {
            let option = document.createElement("option")
            option.text = city.name
            option.value = city.geoname_id
            select_city.add(option)
        }
    } catch {}
}
async function load_countries(country) {
    document.getElementById("select-country").addEventListener("change", load_cities)
    document.getElementById("select-city").classList.add("hidden")
    try {
        const response = await fetch("/api/countries", {
            method: "GET",
            headers: { Accept: "application/json" },
        })
        if (!response.ok) {
            throw Error(response.statusText)
        }
        const data = await response.json()
        let select_country = document.getElementById("select-country")
        for (const [code, name] of data) {
            let option = document.createElement("option")
            option.text = name
            option.value = code
            select_country.add(option)
        }
        select_country.value = country
        await load_cities()
    } catch {}
}
async function load() {
    console.log(Intl.DateTimeFormat().resolvedOptions().timeZone)
    let country = document.querySelector('meta[property="country"]')
    if (!country) {
        country = ""
    } else {
        country = country.content
    }
    await load_countries(country)
    const city = document.querySelector('meta[property="city"]')
    if (city) {
        document.getElementById("select-city").value = city.content
    }
}
window.addEventListener("load", load)
