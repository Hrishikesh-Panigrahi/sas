// ------------------------------- Variables -----------------------------------

let lectures = [];
// Take elements with id starting with weekday and push on to the array.
lectures.push(document.querySelectorAll(`[id^="monday"]`));
lectures.push(document.querySelectorAll(`[id^="tuesday"]`));
lectures.push(document.querySelectorAll(`[id^="wednesday"]`));
lectures.push(document.querySelectorAll(`[id^="thursday"]`));
lectures.push(document.querySelectorAll(`[id^="friday"]`));
lectures.push(document.querySelectorAll(`[id^="saturday"]`));

// If 'timetable' present in storage, disable the create button
if ((localStorage.getItem('timetable') != null) && (document.getElementById("create-btn") != null)) {
    document.getElementById("create-btn").disabled = true;
}

// structure of JSON object.
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
        },
        "saturday": {
            "slots": []
        }
    }
};

// ------------------------------ Functions ------------------------------------

// ----------------------- Save Data to json object ----------------------------
// dictionary 'dict' is used to store lecture data until pushed to 'slots' array
// in time_table object. Store in browser storage as timetable and disable button.
const createTimeTable = () => {
    let time_slot = ["8:00-9:00", "9:00-10:00", "10:00-11:00", 
                    "11:15-13:15", "14:00-15:00", "15:00-16:00",
                    "16:00-17:00", "11:15-13:15", "11:15-13:15"];
    let tt = "";
    let i = 0;
    Object.keys(time_table.schedule).forEach(function(key) {
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
    document.getElementById("create-btn").disabled = true;
    window.location.reload();
};

// ----------------------- Load Data from json object --------------------------
// Parse 'timetable' object if available. Change HTML of table to output 
// appropriate lectures & teachers.Displays on CreateTimeTable page once
// time table is created.
const loadData = () => {
    if (localStorage.getItem('timetable') == null) {
        console.log("nothing to show");
        return;
    }
    time_table = JSON.parse(localStorage.getItem('timetable'));
    console.log(time_table)
    let i = 0;
    Object.keys(time_table.schedule).forEach(function(key) {
        for (let j = 0; j < 9; j++) {
            lectures[i][j].innerHTML = time_table.schedule[key].slots[j].course;
            lectures[i][j].previousElementSibling.innerHTML = time_table.schedule[key].slots[j].teacher;
        }
        i += 1;
    });
};

// ---------------- Edit json object data into temp file -----------------------
// dictionary 'dict' is used to store lecture data until pushed to 'slots' array
// in 'flush_tt' object. Store in browser storage as timetable and disable button.
const flushableData = (_state,_date,_time) => {
    let time_slot = ["8:00-9:00", "9:00-10:00", "10:00-11:00", 
                    "11:15-13:15", "14:00-15:00", "15:00-16:00",
                    "16:00-17:00", "11:15-13:15", "11:15-13:15"];
    let tt = "";
    let i = 0;

    console.log(_state,parseInt(_date),parseInt(_time));
    // time_table = JSON.parse(localStorage.getItem('timetable'));
    // Object.keys(time_table.schedule).forEach(function(key) {
    //     for (let j = 0; j < 9; j++) {
    //         let dict = {
    //             time: time_slot[j],
    //             course: lectures[i][j].childNodes[1].value,
    //             teacher: "yes"
    //         };
    //         time_table.schedule[key].slots.push(dict);
    //     }
    //     i += 1;
    // });
    // tt = JSON.stringify(time_table);
    // console.log(tt);
    // localStorage.setItem('timetable', tt);
    // create_btn.disabled = true;
    // window.location.reload();
};

// -------------- Render buttons for release/request click event ---------------
// 
const editTimeTable = ()=> {
    let sub_teacher = document.getElementById('subject').childNodes[1];
    if (localStorage.getItem('timetable') == null) {
        console.log("nothing to show");
        // TODO: Add redirect to createTT page
        return;
    }
    const reloadPage = ()=> {
        window.location.reload();
    };
    time_table = JSON.parse(localStorage.getItem('timetable'));
    sub_teacher.addEventListener('change',reloadPage)
    let i = 0;
    Object.keys(time_table.schedule).forEach(function(key) {
        for (let j = 0; j < 9; j++) {
            lectures[i][j].innerHTML = time_table.schedule[key].slots[j].course;
            lectures[i][j].classList.add("d-flex","flex-column","align-items-center");            
            lectures[i][j].previousElementSibling.innerHTML = "Teacher";
            let request = "";
            if(sub_teacher.value == time_table.schedule[key].slots[j].course){
                request = '<button type="submit" onclick="flushableData(\'rel\','+ i +','+ j +');" class="btn btn-warning btn-icon-split">\
                                <span class="icon text-white-50">\
                                    <i class="fa fa-times"></i>\
                                </span>\
                                <span class="text">Release</span>\
                            </button>';
            }
            else{
                request = '<button type="submit" onclick="flushableData(\'req\','+ i +','+ j +');" class="btn btn-info btn-icon-split">\
                                <span class="icon text-white-50">\
                                    <i class="fas fa-plus"></i>\
                                </span>\
                                <span class="text">Request</span>\
                            </button>';
            }
            lectures[i][j].innerHTML += request;
        }
        i += 1;
    });
};
