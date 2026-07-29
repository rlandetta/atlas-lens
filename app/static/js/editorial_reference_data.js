window.ATLAS_EDITORIAL_REFERENCE = {
    countries: {
        Argentina: {
            capital: "Buenos Aires",
            variants: ["Buenos Aires"]
        },
        Bolivia: {
            capital: "La Paz",
            variants: ["La Paz", "Sucre"]
        },
        Belice: {
            capital: "Belmopán",
            variants: ["Belmopán", "Belmopan"]
        },
        Brasil: {
            capital: "Brasília",
            variants: ["Brasilia", "Brasília"]
        },
        Chile: {
            capital: "Santiago",
            variants: ["Santiago", "Santiago de Chile"]
        },
        Colombia: {
            capital: "Bogotá",
            variants: ["Bogota", "Bogotá"]
        },
        "Costa Rica": {
            capital: "San José",
            variants: ["San José", "San Jose"]
        },
        Cuba: {
            capital: "La Habana",
            variants: ["La Habana", "Habana", "Havana"]
        },
        Ecuador: {
            capital: "Quito",
            variants: ["Quito"]
        },
        "El Salvador": {
            capital: "San Salvador",
            variants: ["San Salvador"]
        },
        Guatemala: {
            capital: "Ciudad de Guatemala",
            variants: ["Ciudad de Guatemala", "Guatemala", "Guatemala City"]
        },
        Guyana: {
            capital: "Georgetown",
            variants: ["Georgetown"]
        },
        Haití: {
            capital: "Puerto Príncipe",
            variants: ["Puerto Príncipe", "Puerto Principe", "Port-au-Prince"]
        },
        Honduras: {
            capital: "Tegucigalpa",
            variants: ["Tegucigalpa"]
        },
        México: {
            capital: "Ciudad de México",
            variants: ["Ciudad de México", "Mexico", "México", "Mexico City", "CDMX"]
        },
        Nicaragua: {
            capital: "Managua",
            variants: ["Managua"]
        },
        Panamá: {
            capital: "Ciudad de Panamá",
            variants: ["Ciudad de Panamá", "Ciudad de Panama", "Panamá", "Panama"]
        },
        Paraguay: {
            capital: "Asunción",
            variants: ["Asunción", "Asuncion"]
        },
        Perú: {
            capital: "Lima",
            variants: ["Lima"]
        },
        "Puerto Rico": {
            capital: "San Juan",
            variants: ["San Juan"]
        },
        "República Dominicana": {
            capital: "Santo Domingo",
            variants: ["Santo Domingo"]
        },
        Surinam: {
            capital: "Paramaribo",
            variants: ["Paramaribo"]
        },
        "Estados Unidos": {
            capital: "Washington D. C.",
            variants: ["Washington", "Washington D. C.", "Washington DC"]
        },
        China: {
            capital: "Beijing",
            variants: ["Beijing", "Pekín", "Pekin"]
        },
        Uruguay: {
            capital: "Montevideo",
            variants: ["Montevideo"]
        },
        Venezuela: {
            capital: "Caracas",
            variants: ["Caracas"]
        }
    }
};

(() => {
    const reference = window.ATLAS_EDITORIAL_REFERENCE;

    const normalizeValue = (value) => (
        (value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase()
            .replace(/d\.\s*c\./g, "dc")
            .replace(/[^a-z0-9\s]/g, " ")
            .replace(/\s+/g, " ")
            .trim()
    );

    const normalizeCity = (value) => {
        const key = normalizeValue(value);
        const variants = {
            beijing: "beijing",
            pekin: "beijing",
            brasilia: "brasilia",
            mexico: "ciudad de mexico",
            "ciudad de mexico": "ciudad de mexico",
            "mexico city": "ciudad de mexico",
            cdmx: "ciudad de mexico",
            washington: "washington dc",
            "washington dc": "washington dc"
        };

        return variants[key] || key;
    };

    const getCountryEntry = (country) => {
        const countryKey = normalizeValue(country);
        return Object.entries(reference.countries).find(([name]) => (
            normalizeValue(name) === countryKey
        )) || null;
    };

    reference.get_capital_for_country = (country) => {
        const entry = getCountryEntry(country);
        return entry ? entry[1].capital : null;
    };

    reference.is_capital = (city, country) => {
        const entry = getCountryEntry(country);
        if (!entry) {
            return false;
        }

        const cityKey = normalizeCity(city);
        const capitalData = entry[1];
        return (capitalData.variants || [capitalData.capital]).some((variant) => (
            normalizeCity(variant) === cityKey
        ));
    };

    reference.find_country_for_capital = (city) => {
        const cityKey = normalizeCity(city);
        const entry = Object.entries(reference.countries).find(([, capitalData]) => (
            (capitalData.variants || [capitalData.capital]).some((variant) => (
                normalizeCity(variant) === cityKey
            ))
        ));

        return entry ? entry[0] : null;
    };

    reference.validate_city_country = (city, country) => {
        const isCapital = reference.is_capital(city, country);
        const capitalCountry = reference.find_country_for_capital(city);
        const countryKey = normalizeValue(country);
        const capitalCountryKey = normalizeValue(capitalCountry);
        const hasWarning = Boolean(
            capitalCountry
            && capitalCountryKey
            && capitalCountryKey !== countryKey
        );

        return {
            is_capital: isCapital,
            city_country_warning: hasWarning
                ? `La ciudad ingresada es conocida como capital de ${capitalCountry}, pero el país seleccionado es ${country}.`
                : "",
            capital_country: capitalCountry
        };
    };
})();
