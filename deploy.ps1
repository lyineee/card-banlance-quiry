$remotePath = "~/dev/card-bill/";
$composeFilePath = "~/dev/"
$fileList = "main.py", # main
            "student_card.py",
            "requirements.txt", # pip
            "dockerfile" # docker
foreach ($item in $fileList) {
    scp -r $item server:$remotePath;
}
# ssh server ("cd {0};docker-compose down --rmi local;docker-compose up -d" -f $remotePath)
ssh server ("cd {0}; docker-compose up --build -d card-bill" -f $composeFilePath)