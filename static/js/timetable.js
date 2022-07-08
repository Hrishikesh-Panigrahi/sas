let lectures = [];
lectures.push(document.querySelectorAll(`[id^="monday"]`));
lectures.push(document.querySelectorAll(`[id^="tuesday"]`));
lectures.push(document.querySelectorAll(`[id^="wednesday"]`));
lectures.push(document.querySelectorAll(`[id^="thursday"]`));
lectures.push(document.querySelectorAll(`[id^="friday"]`));
lectures.push(document.querySelectorAll(`[id^="saturday"]`));


// ----------------------- Get Site Cookies ----------------------------
function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}


// ----------------------- Save Data to json object ----------------------------
let submit_btn = document.getElementById("submit-btn");
if (localStorage.getItem('timetable') != null) {
    submit_btn.disabled = true;
}
let time_table = {
    "class": "class_id",
    "schedule": {
        "monday": {
            "slots": [  //{"time": "slot_time",
                // "course": "course_id",
                // "teacher": "teacher_id"},
            ]
        },
        "tuesday": {
            "slots": []
        },
        "wednesday": {
            "slots": []
        },
        "thursday": {
            "slots": []
        },
        "friday": {
            "slots": []
        }
    }
};
let time_slot = ["8:00-9:00", "9:00-10:00", "10:00-11:00", "11:15-13:15", "14:00-15:00", "15:00-16:00", "16:00-17:00", "11:15-13:15", "11:15-13:15"];
let tt = "";
const parseData = () => {
    let i = 0;
    Object.keys(time_table.schedule).forEach(function (key) {
        for (let j = 0; j < 9; j++) {
            let dict = {
                time: time_slot[j],
                course: lectures[i][j].childNodes[1].value,
                teacher: "yes"
            };
            time_table.schedule[key].slots.push(dict);
        }
        i += 1;
    });
    tt = JSON.stringify(time_table);
    console.log(tt);
    localStorage.setItem('timetable', tt);
    submit_btn.disabled = true;
};
submit_btn.addEventListener('click', parseData);

// ----------------------- Load Data from json object --------------------------

// let time_slot = ["8:00-9:00", "9:00-10:00", "10:00-11:00", "11:15-13:15", "14:00-15:00", "15:00-16:00", "16:00-17:00", "11:15-13:15", "11:15-13:15"];
const loadData = () => {
    if (localStorage.getItem('timetable') == null) {
        // time_table = { "class": "class_id", "schedule": { "monday": { "slots": [{ "time": "8:00-9:00", "course": "FREE", "teacher": "yes" }, { "time": "9:00-10:00", "course": "EM", "teacher": "yes" }, { "time": "10:00-11:00", "course": "OS", "teacher": "yes" }, { "time": "11:15-13:15", "course": "DBMS", "teacher": "yes" }, { "time": "14:00-15:00", "course": "AOA", "teacher": "yes" }, { "time": "15:00-16:00", "course": "DBMS", "teacher": "yes" }, { "time": "16:00-17:00", "course": "EM", "teacher": "yes" }, { "time": "11:15-13:15", "course": "MP", "teacher": "yes" }, { "time": "11:15-13:15", "course": "AOA", "teacher": "yes" }] }, "tuesday": { "slots": [{ "time": "8:00-9:00", "course": "FREE", "teacher": "yes" }, { "time": "9:00-10:00", "course": "DBMS", "teacher": "yes" }, { "time": "10:00-11:00", "course": "AOA", "teacher": "yes" }, { "time": "11:15-13:15", "course": "PYTHON", "teacher": "yes" }, { "time": "14:00-15:00", "course": "MP", "teacher": "yes" }, { "time": "15:00-16:00", "course": "OS", "teacher": "yes" }, { "time": "16:00-17:00", "course": "EM", "teacher": "yes" }, { "time": "11:15-13:15", "course": "DBMS", "teacher": "yes" }, { "time": "11:15-13:15", "course": "MP", "teacher": "yes" }] }, "wednesday": { "slots": [{ "time": "8:00-9:00", "course": "FREE", "teacher": "yes" }, { "time": "9:00-10:00", "course": "PYTHON", "teacher": "yes" }, { "time": "10:00-11:00", "course": "EM", "teacher": "yes" }, { "time": "11:15-13:15", "course": "AOA", "teacher": "yes" }, { "time": "14:00-15:00", "course": "OS", "teacher": "yes" }, { "time": "15:00-16:00", "course": "PROJECT", "teacher": "yes" }, { "time": "16:00-17:00", "course": "PROJECT", "teacher": "yes" }, { "time": "11:15-13:15", "course": "OS", "teacher": "yes" }, { "time": "11:15-13:15", "course": "PYTHON", "teacher": "yes" }] }, "thursday": { "slots": [{ "time": "8:00-9:00", "course": "FREE", "teacher": "yes" }, { "time": "9:00-10:00", "course": "MP", "teacher": "yes" }, { "time": "10:00-11:00", "course": "EM", "teacher": "yes" }, { "time": "11:15-13:15", "course": "OS", "teacher": "yes" }, { "time": "14:00-15:00", "course": "DBMS", "teacher": "yes" }, { "time": "15:00-16:00", "course": "PYTHON", "teacher": "yes" }, { "time": "16:00-17:00", "course": "MENTORING", "teacher": "yes" }, { "time": "11:15-13:15", "course": "PYTHON", "teacher": "yes" }, { "time": "11:15-13:15", "course": "DBMS", "teacher": "yes" }] }, "friday": { "slots": [{ "time": "8:00-9:00", "course": "FREE", "teacher": "yes" }, { "time": "9:00-10:00", "course": "AOA", "teacher": "yes" }, { "time": "10:00-11:00", "course": "MP", "teacher": "yes" }, { "time": "11:15-13:15", "course": "MP", "teacher": "yes" }, { "time": "14:00-15:00", "course": "PROJECT", "teacher": "yes" }, { "time": "15:00-16:00", "course": "PROJECT", "teacher": "yes" }, { "time": "16:00-17:00", "course": "REMEDY", "teacher": "yes" }, { "time": "11:15-13:15", "course": "AOA", "teacher": "yes" }, { "time": "11:15-13:15", "course": "OS", "teacher": "yes" }] } } };
        console.log("nothing to show");
        return;
    }
    time_table = JSON.parse(localStorage.getItem('timetable'));
    console.log(time_table)
    let i = 0;
    Object.keys(time_table.schedule).forEach(function (key) {
        for (let j = 0; j < 9; j++) {
            // time: time_slot[j],
            lectures[i][j].innerHTML = time_table.schedule[key].slots[j].course,
                lectures[i][j].previousElementSibling.innerHTML = time_table.schedule[key].slots[j].teacher
        }
        i += 1;
    });
};



submit_btn.addEventListener('click', async () => {
    const csrftoken = getCookie('csrftoken');
    tt = localStorage.getItem('timetable');
    let res = await fetch('http://localhost:8000/timetable/CreateTimeTable', {
        method: 'POST',
        headers: { "X-CSRFToken": csrftoken },
        body: tt
    });
    res = await res.json();
})