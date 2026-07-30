async function openMotor(){
    await fetch("/motor/open",{
        method:"POST"
    });
}

async function closeMotor(){
    await fetch("/motor/close",{
        method:"POST"
    });
}

async function rotateMotor() {
    const rotation = parseInt(
        document.getElementById("rotation").value
    );
    const response = await fetch("/motor/rotate", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            rotation: rotation
        })
    });
    const result = await response.json();
    document.getElementById("status").innerHTML =
        `Moved ${result.rotation} steps`;
}