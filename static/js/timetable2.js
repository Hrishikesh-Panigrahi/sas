const errTxt = $("#err")
errTxt.html("").hide();

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

let time_table = {
    "class": "class_id",
    "schedule": {
        "Monday": [
            //{
            // "course": "course_id",
            // "teacher": "teacher_id",
            // "type": "slot_type",
            // "batch": "batch",
            // "weekday": "day"
            // "start_time": "slot_time",
            // "end_time": "slot_time",
            // },
            // Demo object
            // { course: 'Python', type: 'Lecture', batch: 'All', start_time: '09:00', end_time: '10:00' }
        ],
        "Tuesday": [],
        "Wednesday": [],
        "Thursday": [],
        "Friday": [],
        "Saturday": []
    }
};

if (t_json)
    time_table = t_json

const sortByKey = (a, b) => {
    let keyA = a.start_time
    let keyB = b.start_time

    // Compare
    if (keyA < keyB) return -1;
    if (keyA > keyB) return 1;
    return 0;
}

$("#start-time").on("change", () => {
    let temp = new Date("01-01-2017 " + $("#start-time").val())
    temp.setHours(temp.getHours() + 1)
    temp = temp.toTimeString().split(' ')[0].slice(0, 5);
    $("#end-time").val(temp)
})

$("#add-btn").on("click", async () => {
    const course = $(".select-form").val();
    const type = $("#slot-type").val();
    const batch = $("#batch").val();
    const weekday = $("#weekday").val();
    const start_time = $("#start-time").val();
    const end_time = $("#end-time").val();

    let slot = { course, type, batch, start_time, end_time }

    if (course == "" || type == "" || batch == "" || weekday == "" || start_time == "" || end_time == "")
        errTxt.html("All fields must be populated").show();
    else {
        console.log(time_table);
        errTxt.html("").hide();
        time_table.schedule[weekday].push(slot);
        time_table.schedule[weekday].sort(sortByKey)
        /* 
            TODO: send time_table to server
            save time)table to localstorage
        */
        const csrftoken = getCookie('csrftoken');
        tt = JSON.stringify(time_table);
        // let res = await fetch('http://localhost:8000/timetable/CreateTimeTable', {
        //     method: 'POST',
        //     headers: { "X-CSRFToken": csrftoken },
        //     body: tt
        // });
        // res = await res.json();
    }
})

// let del_btns = document.querySelectorAll("[id$=del-btn]");
let tabby = "";
fetch(path)
.then((resp) => resp.json())
.then((json) =>{tabby = json})

const delSlot = async (weekday,time) => {
    console.log(weekday,time)
    console.log(tabby['schedule'][weekday]['slots'][time]);
    tabby['schedule'][weekday]['slots'][time]['course'] = 'FREE';
    tabby['schedule'][weekday]['slots'][time]['teacher'] = 'NOPE';
    console.log(tabby['schedule'][weekday]['slots'][time]);
    tabby = JSON.stringify(tabby);
    const csrftoken = getCookie('csrftoken');
    let res = await fetch('http://localhost:8000/timetable/test', {
        method: 'POST',
        headers: {
            "X-CSRFToken": csrftoken 
        },
        body: tabby
    });
    res = await res.json();
    console.log(res);
    // console.log(tabby);
}